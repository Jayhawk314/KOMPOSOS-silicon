# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
ESMFold PyTorch 2.x Compatibility Fix

Fixes RuntimeError: one_hot is only applicable to index tensor of type LongTensor
by patching transformers library's ESMFold code to cast tensors to long.
"""

import torch
import torch.nn.functional as F

# Monkey patch torch.nn.functional.one_hot to auto-cast to long
_original_one_hot = F.one_hot

def patched_one_hot(tensor, num_classes=-1):
    """
    Patched one_hot that auto-casts input to long.

    PyTorch 2.x requires LongTensor, but ESMFold passes IntTensor.
    """
    if tensor.dtype != torch.long:
        tensor = tensor.long()
    return _original_one_hot(tensor, num_classes)

# Apply global patch
torch.nn.functional.one_hot = patched_one_hot
F.one_hot = patched_one_hot

print("ESMFold compatibility patch applied successfully")
print("  Fixed: one_hot LongTensor requirement for PyTorch 2.x")
