# Buffer type to build an obs to
import numpy as np
import torch

from .gamestate.vec import Vec


class ObsBuffer:
    def __init__(self, zeros_len=0):
        self._list = [0.0] * zeros_len

    def __add__(self, val):
        clone = ObsBuffer()
        clone._list = self._list.copy()
        clone += val
        return clone

    def __iadd__(self, val):
        if isinstance(val, int) or isinstance(val, float) or isinstance(val, bool):
            self._list.append(float(val))
        elif isinstance(val, Vec):
            self._list += [val.x, val.y, val.z]
        elif isinstance(val, np.ndarray):
            self._list += val.astype(np.float32).tolist()
        elif isinstance(val, list):
            for subval in val:
                self += subval
        elif isinstance(val, ObsBuffer):
            self._list += val._list.copy()
        elif isinstance(val, np.float32):
            self._list.append(float(val))
        elif isinstance(val, np.bool_):
            self._list.append(float(bool(val)))
        else:
            assert False, f"Unimplemented type for ObsBuffer: {val.__class__}"
        return self

    def fill_zero(self):
        self._list = [0.0] * len(self._list)

    def get_np(self) -> np.ndarray:
        return np.array(self._list, dtype=np.float32)

    def get_tensor(self, device: str | torch.device | None = None) -> torch.Tensor:
        """Return observation as a torch.float32 1D tensor on the requested device.

        Using this avoids an intermediate NumPy allocation and lets callers
        directly feed the tensor to TorchScript models.
        """
        if device is None:
            return torch.tensor(self._list, dtype=torch.float32)
        return torch.tensor(self._list, dtype=torch.float32, device=device)

    def __len__(self) -> int:
        return len(self._list)
