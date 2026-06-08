# Auto-improvement #201
# Module: tool_routing
# Improvement: add_route_learning
# Description: Learn from successful routes
# Timestamp: 2026-06-08T03:20:46.041434+00:00


def learn_route(task_type, tool, success):
    history = load_route_history()
    key = f"{task_type}:{tool}"
    if key not in history:
        history[key] = {"success": 0, "failure": 0}
    if success:
        history[key]["success"] += 1
    else:
        history[key]["failure"] += 1
    save_route_history(history)

