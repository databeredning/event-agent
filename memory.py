def build_memory(experience):
    if experience is None:
        return None

    return {
        "type": "previous_experience",
        "created_at": experience["created_at"],
        "trigger": experience["trigger"],
        "context": experience["context"],
        "outcome": experience["outcome"],
        "execution": experience["execution"],
    }