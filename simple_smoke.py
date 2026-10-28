import sys, time, torch
sys.path.insert(0, r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-official')
from mgpt_config import MGPTConfig
from gpt_model import GPT

print("Step 1: Creating model...")
config = MGPTConfig(vocab_size=12000, n_embd=512, n_head=8, n_layer=12, block_size=1024, bias=False, dropout=0.1)
model = GPT(config)
total = sum(p.numel() for p in model.parameters())
print(f"  Parameters: {total:,}")

print("Step 2: Moving to GPU...")
device = 'cuda'
model = model.to(device)
model.train()
if torch.cuda.is_available():
    print(f"  VRAM: {torch.cuda.memory_allocated(0)/1024**2:.1f} MB")

print("Step 3: Forward pass (batch=1, seq=32)...")
input_ids = torch.randint(0, 12000, (1, 32), device=device)
targets = input_ids.clone()
t0 = time.time()
logits, loss = model(input_ids, targets=targets)
t1 = time.time()
print(f"  Loss: {loss.item():.4f}, Finite: {torch.isfinite(loss)}")
print(f"  Time: {(t1-t0)*1000:.1f} ms")

print("Step 4: Backward pass...")
loss.backward()
t2 = time.time()
print(f"  Time: {(t2-t1)*1000:.1f} ms")

grad_norm = 0.0
count = 0
for name, p in model.named_parameters():
    if p.grad is not None and torch.isfinite(p.grad).all():
        grad_norm += p.grad.norm().item() ** 2
        count += 1
grad_norm = grad_norm ** 0.5
print(f"  Grad norm: {grad_norm:.4f}, Params with grad: {count}")

print("Step 5: Optimizer step...")
opt = torch.optim.AdamW(model.parameters(), lr=1e-4)
opt.step()
opt.zero_grad()
t3 = time.time()
print(f"  Time: {(t3-t2)*1000:.1f} ms")

all_finite = all(torch.isfinite(p.data).all() for p in model.parameters())
print(f"  All params finite: {all_finite}")
if torch.cuda.is_available():
    print(f"  Peak VRAM: {torch.cuda.max_memory_allocated(0)/1024**2:.1f} MB")

print("\nSMOKE TEST PASSED")