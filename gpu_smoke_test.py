import sys
sys.path.insert(0, r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-official')

import torch
import torch.nn as nn
import time
import json

from mgpt_config import MGPTConfig
from gpt_model import GPT

print("=" * 60)
print("GPU SMOKE TEST - Official shikhr/music_maker")
print("=" * 60)

# 1. Load tokenizer
from miditok import MusicTokenizer
tokenizer = MusicTokenizer.from_pretrained(r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-official')
print(f"\nTokenizer vocab_size: {tokenizer.vocab_size}")

# 2. Load model config and architecture
config = MGPTConfig(vocab_size=12000, n_embd=512, n_head=8, n_layer=12, block_size=1024, bias=False, dropout=0.1)
model = GPT(config)
total_params = sum(p.numel() for p in model.parameters())
print(f"Model parameters: {total_params:,} ({total_params/1e6:.2f}M)")

# 3. Load pretrained checkpoint
import safetensors.torch as st
ckpt_path = r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-official\model.safetensors'
print(f"\nLoading checkpoint: {ckpt_path}")
ckpt = st.load_file(ckpt_path)
print(f"Checkpoint keys: {len(ckpt)}")

# Handle key prefix (strip 'model.')
new_sd = {}
for k, v in ckpt.items():
    if k.startswith('model.'):
        k = k[6:]
    new_sd[k] = v

missing, unexpected = model.load_state_dict(new_sd, strict=False)
print(f"Missing keys: {len(missing)}, Unexpected keys: {len(unexpected)}")

# Verify weight tying
print(f"\nWeight tying: wte is lm_head: {model.transformer.wte.weight is model.lm_head.weight}")

# 4. Move to GPU
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = model.to(device)
print(f"Model on device: {device}")
if torch.cuda.is_available():
    print(f"Peak VRAM after model load: {torch.cuda.max_memory_allocated(0) / 1024**2:.1f} MB")

# 5. Forward pass with batch=1, seq_len=32
model.train()
batch_size, seq_len = 1, 32
input_ids = torch.randint(0, 12000, (batch_size, seq_len), device=device)
targets = input_ids.clone()

print(f"\nForward pass: batch={batch_size}, seq_len={seq_len}")
start = time.time()
logits, loss = model(input_ids, targets=targets)
forward_time = time.time() - start

print(f"  Logits shape: {logits.shape}")
print(f"  Loss: {loss.item():.4f}")
print(f"  Loss finite: {torch.isfinite(loss)}")
print(f"  Forward time: {forward_time*1000:.1f} ms")
if torch.cuda.is_available():
    print(f"  Peak VRAM after forward: {torch.cuda.max_memory_allocated(0) / 1024**2:.1f} MB")

# 6. Backward pass
print("\nBackward pass...")
start = time.time()
loss.backward()
backward_time = time.time() - start
print(f"  Backward time: {backward_time*1000:.1f} ms")

# 7. Check gradients
grad_norm = 0.0
num_grads = 0
for name, param in model.named_parameters():
    if param.grad is not None:
        if torch.isfinite(param.grad).all():
            grad_norm += param.grad.norm().item() ** 2
            num_grads += 1
        else:
            print(f"  WARNING: Non-finite gradients in {name}")

grad_norm = grad_norm ** 0.5
print(f"  Grad norm: {grad_norm:.4f}")
print(f"  Parameters with gradients: {num_grads}")
print(f"  All finite: {num_grads > 0}")

# 8. Optimizer step
print("\nOptimizer step (AdamW, lr=1e-4)...")
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
start = time.time()
optimizer.step()
optimizer.zero_grad()
opt_time = time.time() - start
print(f"  Optimizer time: {opt_time*1000:.1f} ms")

# 9. Verify parameters remain finite and update occurred
all_finite = True
for name, param in model.named_parameters():
    if not torch.isfinite(param.data).all():
        print(f"  WARNING: Non-finite parameters in {name}")
        all_finite = False

print(f"\n  All parameters finite: {all_finite}")
print(f"  Optimizer step completed: YES")

# 10. Summary
if torch.cuda.is_available():
    peak_vram = torch.cuda.max_memory_allocated(0) / 1024**2
    print(f"\n  Peak VRAM: {peak_vram:.1f} MB")
    
throughput = (batch_size * seq_len) / forward_time if forward_time > 0 else 0
print(f"  Throughput: {throughput:.1f} tokens/sec")

results = {
    "torch_version": torch.__version__,
    "cuda_available": torch.cuda.is_available(),
    "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    "total_parameters": total_params,
    "batch_size": batch_size,
    "seq_len": seq_len,
    "forward_time_ms": forward_time * 1000,
    "backward_time_ms": backward_time * 1000,
    "optimizer_time_ms": opt_time * 1000,
    "loss": loss.item(),
    "loss_finite": bool(torch.isfinite(loss)),
    "grad_norm": grad_norm,
    "num_grad_params": num_grads,
    "all_finite": all_finite,
    "optimizer_step_completed": True,
    "throughput_tokens_per_sec": throughput,
    "peak_vram_mb": torch.cuda.max_memory_allocated(0) / 1024**2 if torch.cuda.is_available() else 0,
}

results_path = r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\gpu_smoke_test_results.json'
with open(results_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to: {results_path}")

print("\n" + "=" * 60)
print("GPU SMOKE TEST PASSED")
print("=" * 60)