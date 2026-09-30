# Changelog: jarvo

## Niewydane
- Skill `writing-for-agents` (mattpocock/skills, MIT): warsztat pisania dokumentów dla agentów (wskaźniki kontekstu, hierarchia informacji, kryteria ukończenia). `fleet-improvement`: zanim zaproponujesz zmianę w SOUL albo skillu, `writing-for-agents` (gdzie umieścić, opis jako wskaźnik, kryterium ukończenia).
- Kontrakt zlecenia (wspólny): nie osłabiam kontroli, żeby zaliczyć DoD (za ECC loop-design-check); poprawki po recenzji z pytaniem przy niejasnym punkcie i sprzeciwem z dowodem przy błędnym (za superpowers receiving-code-review); reguła 17: zgoda A2 przypięta do odcisku wersji plików (`scripts/odcisk.py`, za ECC operator-approval-loop). Sędzia (`sdlc-review` 4b): sprzeciw z dowodem zamyka punkt, osłabiona kontrola blokuje, prośba o A2 bez odcisku wraca do poprawki. `decision-queue`: pytanie i decyzja A2 z odciskiem. `dispatch-playbook`: karta `goal_mode` nazywa, czego nie wolno ruszyć.
- Czat Jarvo HQ (`platform_toolsets.api_server`) ustawiony jawnie: te same narzędzia co na Telegramie (bez `clarify`). Wcześniej Hermes dawał tu terminal bez kanbana, więc z HQ nie dało się rozdać kart.

## 0.1.0 (2026-09-26)
- Pierwsza wersja: SOUL Main Judge, 10 skilli floty + roster, sędzia `sdlc-review` z rubrykami,
  patrol i raporty bez modelu (bramka `wakeAgent`), 4 rutyny cron.
