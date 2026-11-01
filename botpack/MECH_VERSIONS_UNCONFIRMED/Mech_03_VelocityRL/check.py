import torch
import os

cur_dir = os.path.dirname(os.path.realpath(__file__))
checkpoint = torch.load(os.path.join(cur_dir, "PPO_POLICY.pt"), map_location="cpu")

print("Model structure:")
for key, tensor in checkpoint.items():
    print(f"{key}: {tensor.shape}")

# Find the final layer to get action count
final_weights = [k for k in checkpoint.keys() if 'weight' in k][-1]
actual_num_actions = checkpoint[final_weights].shape[0]
print(f"Actual number of actions: {actual_num_actions}")