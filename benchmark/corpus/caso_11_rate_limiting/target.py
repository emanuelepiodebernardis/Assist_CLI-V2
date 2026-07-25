"""Rate limiting: una richiesta e' consentita solo sotto entrambi i
limiti configurati (al minuto e all'ora)."""


def richiesta_consentita(
    richieste_ultimo_minuto: int,
    richieste_ultima_ora: int,
    limite_minuto: int = 10,
    limite_ora: int = 100,
) -> bool:
    """Ritorna True se la richiesta rispetta sia il limite al minuto
    sia quello orario.

    Bug: usa ``or`` invece di ``and``, quindi basta rispettare UNO
    solo dei due limiti per essere consentita.
    """
    sotto_limite_minuto = richieste_ultimo_minuto < limite_minuto
    sotto_limite_ora = richieste_ultima_ora < limite_ora
    return sotto_limite_minuto or sotto_limite_ora
