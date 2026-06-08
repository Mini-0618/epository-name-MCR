# Auto-improvement #106
# Module: crash_recovery
# Improvement: add_checkpoint_rotation
# Description: Rotate old checkpoints
# Timestamp: 2026-06-08T03:20:45.982752+00:00


def rotate_checkpoints(checkpoint_dir, keep=10):
    files = sorted(Path(checkpoint_dir).glob("ckpt-*.json"))
    if len(files) > keep:
        for f in files[:-keep]:
            f.unlink()

