"""Controllo se un utente puo' completare il checkout di un ordine."""


def puo_fare_checkout(carrello_pieno: bool, pagamento_valido: bool) -> bool:
    """Consente il checkout solo se il carrello e' pieno E il
    pagamento e' valido.

    Bug: la condizione usa ``or`` invece di ``and``, permettendo il
    checkout anche quando e' soddisfatto un solo requisito.
    """
    if carrello_pieno or pagamento_valido:
        return True
    return False
