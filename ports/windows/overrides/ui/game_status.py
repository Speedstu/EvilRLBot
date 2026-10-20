"""Windows version uses the native RLBot V5 Steam/Epic launcher."""
def inspect_game():
    return {"platform": "Windows", "launcher": "Epic/Steam", "managed_by": "RLBotServer"}
def explain_game_status(status):
    return "Install Rocket League through Steam or Epic Games and choose it in Match Settings."
