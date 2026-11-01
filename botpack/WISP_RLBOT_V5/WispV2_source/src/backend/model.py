import enum
from pathlib import Path

import torch

# Ensure gradients are globally disabled for inference-only runtime
torch.set_grad_enabled(False)


class ActivationType(enum.Enum):
    RELU = torch.nn.ReLU
    LEAKY_RELU = torch.nn.LeakyReLU
    GELU = torch.nn.GELU
    SIGMOID = torch.nn.Sigmoid
    TANH = torch.nn.Tanh


def _load_torchscript_module(
    model_path: Path, device: torch.device
) -> torch.jit.ScriptModule:
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    module = torch.jit.load(str(model_path), map_location=device)
    module.eval()
    return module


def _reconstruct_sequential_from_jit(
    module: torch.jit.ScriptModule, activation_type: "ActivationType"
) -> torch.nn.Sequential:
    """
    Rebuilds a Python nn.Sequential using the saved parameters from a TorchScript module.
    Mirrors the previous implementation used in this repository, supporting Linear,
    LayerNorm, and parameterless activations inferred by count.
    """
    result = torch.nn.Sequential()

    # Skip first (top-level) and iterate child modules
    mods = [m for m in module.modules()][1:]
    for mod in mods:
        named_params = [p for p in mod.named_parameters()]
        num_params = len(named_params)

        if num_params == 2:
            # Either Linear layer or LayerNorm; infer by tensor shapes
            assert named_params[0][0] == "weight"
            assert named_params[1][0] == "bias"
            weight = named_params[0][1]
            bias = named_params[1][1]

            weight_shape = weight.shape
            bias_shape = bias.shape

            if len(weight_shape) == 2 and len(bias_shape) == 1:
                # Linear layer
                assert weight_shape[0] == bias_shape[0]
                layer = torch.nn.Linear(weight_shape[1], weight_shape[0])
            elif len(weight_shape) == 1 and len(bias_shape) == 1:
                # LayerNorm
                assert weight_shape[0] == bias_shape[0]
                layer = torch.nn.LayerNorm(weight_shape[0])
            else:
                raise AssertionError(
                    f"Unknown weight/bias shapes: {weight_shape}/{bias_shape}"
                )

            layer.load_state_dict(mod.state_dict())
            result.append(layer)

        elif num_params == 0:
            # Activation function (parameterless)
            result.append(activation_type.value())
        else:
            raise AssertionError(f"Unknown module param count: {num_params}")

    result.eval()
    return result


class ModelInfo:
    def __init__(self, path, activation_type: ActivationType):
        # activation_type is kept for compatibility with configs; TorchScript already encodes activations
        self.path = Path(path)
        self.activation_type = activation_type


class ModelSet:
    """
    High-performance inference wrapper using TorchScript modules directly.

    This avoids reconstructing Python nn.Sequential graphs and keeps execution mostly
    in the JIT/ATen runtime like the C++ pipeline, improving latency and stability.
    """

    def __init__(
        self,
        policy_info: ModelInfo,
        shared_head_info: ModelInfo | None = None,
        device: str | torch.device = "cpu",
    ) -> None:
        self.device = torch.device(device)

        # Load TorchScript modules; if not directly callable, reconstruct nn.Sequential
        policy_ts = _load_torchscript_module(policy_info.path, self.device)
        # Some saved artifacts may not expose a 'forward' method; detect and rebuild
        if hasattr(policy_ts, "forward"):
            self._policy = policy_ts
        else:
            self._policy = _reconstruct_sequential_from_jit(
                policy_ts, policy_info.activation_type
            ).to(self.device)

        self._shared_head = None
        if shared_head_info is not None:
            sh_ts = _load_torchscript_module(shared_head_info.path, self.device)
            if hasattr(sh_ts, "forward"):
                self._shared_head = sh_ts
            else:
                self._shared_head = _reconstruct_sequential_from_jit(
                    sh_ts, shared_head_info.activation_type
                ).to(self.device)

        # Cached buffers to reduce tiny allocations
        self._action_disabled_logit = torch.tensor(
            -1e10, dtype=torch.float32, device=self.device
        )

    def _forward_logits(self, obs_tensor: torch.Tensor) -> torch.Tensor:
        # Expect shape [N, D] or [D]
        if obs_tensor.dim() == 1:
            obs_tensor = obs_tensor.unsqueeze(0)
        else:
            obs_tensor = obs_tensor.view(obs_tensor.size(0), -1)

        x = obs_tensor
        if self._shared_head is not None:
            x = self._shared_head(x)
        logits = self._policy(x)
        return logits.squeeze(0).view(-1)

    def get_action(
        self,
        obs,
        action_mask,
        deterministic: bool = True,
    ) -> int:
        """
        Compute action index given observation and a boolean mask of valid actions.

        - obs: 1D array-like or torch.Tensor (float32)
        - action_mask: array-like or torch.Tensor of booleans/0-1 with length == num_actions
        - deterministic: if True, returns argmax over masked logits without softmax
        """
        with torch.inference_mode():
            if not torch.is_tensor(obs):
                obs_tensor = torch.as_tensor(
                    obs, dtype=torch.float32, device=self.device
                )
            else:
                obs_tensor = obs.to(device=self.device, dtype=torch.float32)

            logits = self._forward_logits(obs_tensor)

            if not torch.is_tensor(action_mask):
                mask_tensor = torch.as_tensor(action_mask, device=self.device)
            else:
                mask_tensor = action_mask.to(device=self.device)

            # Normalize mask to boolean on device
            if mask_tensor.dtype != torch.bool:
                mask_tensor = mask_tensor.to(dtype=torch.bool)
            mask_tensor = mask_tensor.view(-1)

            if mask_tensor.numel() != logits.numel():
                raise ValueError(
                    f"Action mask length {mask_tensor.numel()} does not match policy output {logits.numel()}"
                )

            # Fallback: if nothing is allowed, allow everything
            if not mask_tensor.any():
                mask_tensor = torch.ones_like(
                    mask_tensor, dtype=torch.bool, device=self.device
                )

            # Apply mask by pushing disabled logits far negative (faster than constructing a full tensor)
            if (~mask_tensor).any():
                logits = logits.clone()  # avoid mutating cached outputs
                logits[~mask_tensor] = self._action_disabled_logit

            if deterministic:
                return int(torch.argmax(logits).item())

            # Sample using logits directly for numerical stability
            # Avoid constructing Python distributions if possible
            from torch.distributions.categorical import Categorical

            dist = Categorical(logits=logits)
            return int(dist.sample().item())
