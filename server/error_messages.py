"""Witzige Error-Messages für den Windows-XP-Style Error-Screen.

Jeder Fehler-Typ hat mehrere Varianten. Bei jedem Crash wird zufällig
eine ausgewählt, damit's nicht langweilig wird.
"""
import random


ERROR_MESSAGES = {
    "network": [
        {
            "title": "Verbindung zu Strava verloren",
            "message": "Der Server antwortet nicht. Vermutlich hat er auch "
                       "keine Lust auf Bergetappen bei dem Wetter.",
        },
        {
            "title": "Kein Signal",
            "message": "Strava ist nicht erreichbar. Bitte prüfe ob dein "
                       "WLAN läuft oder ob Malte wieder am Router gebastelt hat.",
        },
        {
            "title": "Verbindungsabbruch",
            "message": "Das Internet ist wandern gegangen. Es wird "
                       "voraussichtlich zurückkommen wenn es Wetter wird.",
        },
    ],
    "auth": [
        {
            "title": "Token abgelaufen",
            "message": "Dein Zugriff auf Strava ist abgelaufen. Vermutlich "
                       "willst du dich neu anmelden oder Malte damit nerven.",
        },
        {
            "title": "Strava möchte dich nicht mehr kennen",
            "message": "Der API-Token wurde abgelehnt. Möglicherweise musst "
                       "du dein Passwort erneuern oder Kekse mitbringen.",
        },
    ],
    "overload": [
        {
            "title": "Zu viel Watt registriert",
            "message": "Der Strava Display ist zusammengebrochen. Bitte "
                       "vorerst kein Sport mehr machen und Malte kontaktieren.",
        },
        {
            "title": "System überhitzt",
            "message": "Zu viele Höhenmeter auf einmal verarbeitet. Der Pi "
                       "braucht eine Pause. Du auch, ehrlich gesagt.",
        },
        {
            "title": "Fitness-Overflow",
            "message": "Deine Aktivitäten haben den Zähler zum Explodieren "
                       "gebracht. Beeindruckend. Aber jetzt bitte Malte anrufen.",
        },
    ],
    "no_activities": [
        {
            "title": "Keine Aktivitäten gefunden",
            "message": "Strava sagt: 'Wer ist das überhaupt?' Vielleicht mal "
                       "wieder was hochladen oder Ausreden erfinden.",
        },
        {
            "title": "Verdächtige Ruhe",
            "message": "In deinem Strava-Konto herrscht gähnende Leere. "
                       "Auch okay, aber dieses Display wird dann langweilig.",
        },
    ],
    "rate_limit": [
        {
            "title": "Strava sagt: langsam",
            "message": "Zu viele Anfragen an die API. Strava braucht eine "
                       "Kaffeepause. In 15 Minuten geht's weiter.",
        },
    ],
    "generic": [
        {
            "title": "Etwas ist schiefgelaufen",
            "message": "Der Strava Display hat einen unerwarteten Fehler. "
                       "Der klassische 'irgendwas ist kaputt'-Fall.",
        },
        {
            "title": "Kernschmelze verhindert",
            "message": "Ein Problem ist aufgetreten, aber immerhin brennt "
                       "nichts. Malte kann Details in den Logs finden.",
        },
        {
            "title": "Unerwartetes Verhalten",
            "message": "Der Strava Display verhält sich wie ein Rennradfahrer "
                       "im Hochgebirge: verwirrt und langsam.",
        },
    ],
}


def get_error(category: str = "generic") -> tuple[str, str]:
    """Return a random (title, message) tuple for the given error category.

    Categories: network, auth, overload, no_activities, rate_limit, generic.
    Unknown categories fall back to 'generic'.
    """
    variants = ERROR_MESSAGES.get(category, ERROR_MESSAGES["generic"])
    choice = random.choice(variants)
    return choice["title"], choice["message"]
