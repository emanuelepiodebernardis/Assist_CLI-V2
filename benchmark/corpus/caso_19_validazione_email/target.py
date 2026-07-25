"""Validazione di un indirizzo email con normalizzazione degli spazi."""


def email_valida(indirizzo: str) -> bool:
    """Ritorna True se `indirizzo`, ripulito dagli spazi, e' un
    indirizzo email plausibile (contiene '@' e un punto nel dominio).

    Bug: dovrebbe normalizzare l'input con
    ``indirizzo = indirizzo.strip()`` prima del controllo, ma la
    chiamata e' stata sostituita da ``indirizzo.upper()`` il cui
    risultato non viene assegnato a nulla: gli spazi iniziali o
    finali non vengono mai rimossi.
    """
    indirizzo.upper()
    return "@" in indirizzo and "." in indirizzo.split("@")[-1]
