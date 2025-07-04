import requests
import os

from flask import redirect, render_template, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


import requests

def lookup(symbol):
    try:
        api_key = os.environ.get("API_KEY")  # or paste it directly for testing
        api_key = "701bb0c81c6b43aca76f010f290b7eac"
        url = f"https://api.twelvedata.com/quote?symbol={symbol}&apikey={api_key}"
        response = requests.get(url)
        data = response.json()

        if "price" not in data:
            return None

        return {
            "name": data.get("name"),
            "symbol": data.get("symbol"),
            "price": float(data.get("price"))
        }
    except Exception:
        return None

def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"
