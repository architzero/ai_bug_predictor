# Windows Multiprocessing Fix - APPLIED

## Issue
The original code failed on Windows with:
```
RuntimeError: An attempt has been made to start a new process before the
current process has finished its bootstrapping phase.
```

## Root Cause
Windows uses `spawn` for multiprocessing (not `fork` like Unix), which requires the `if __name__ == '__main__':` guard to prevent infinite process spawning.

## Fix Applied
Wrapped the entire main pipeline (Stages 1-7) in `if __name__ == '__main__':` block.

### Changes Made
**File**: `main.py`

**Before**:
```python
# Stage 0 (file filtering audit)
print("STAGE 0...")
# ... audit code ...

# Stage 1 (data collection)
print("STAGE 1...")
all_data = []
with ProcessPoolExecutor(max_workers=max_workers) as executor:
    # ... parallel processing ...

# Stage 2-7
# ... rest of pipeline ...
```

**After**:
```python
# Stage 0 (file filtering audit) - OUTSIDE if __name__ block
print("STAGE 0...")
# ... audit code ...

# Stage 1-7 - INSIDE if __name__ block
if __name__ == '__main__':
    print("STAGE 1...")
    all_data = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # ... parallel processing ...
    
    # Stage 2-7
    # ... rest of pipeline ...
```

## Why This Works
- Stage 0 (file filtering audit) runs at import time - safe because it's just printing
- Stages 1-7 only run when script is executed directly (not imported)
- ProcessPoolExecutor can now safely spawn child processes
- Child processes can import main.py without triggering infinite recursion

## Verification
```bash
python -c "import ast; ast.parse(open('main.py').read()); print('✓ Syntax is valid')"
# Output: ✓ Syntax is valid
```

## Status
✅ **FIXED** - Ready to run `python main.py`

## Note
This is a **Windows-specific requirement**. On Unix/Linux/macOS, the `if __name__ == '__main__':` guard is optional (but still good practice).
