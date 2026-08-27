from app.transcription import context_bias


def test_context_bias_accepts_full_participant_names():
    assert context_bias(["Yanis Zedira", "Aymen Djerad"]) == "Yanis_Zedira,Aymen_Djerad"
