import os
import sqlite3
from flask import Flask, flash, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Configure secret key for sessions (change this to a random secret key)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-this-in-production'

# Custom filter
app.jinja_env.filters["usd"] = usd

# Database connection helper
def get_db():
    conn = sqlite3.connect('finance.db')
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn

def execute_query(query, *args):
    """Execute a query and return results as a list of dictionaries"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(query, args)
    
    # For INSERT queries, return the lastrowid
    if query.strip().upper().startswith('INSERT'):
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result
    
    # For UPDATE/DELETE queries, return number of affected rows
    elif query.strip().upper().startswith(('UPDATE', 'DELETE')):
        result = cursor.rowcount
        conn.commit()
        conn.close()
        return result
    
    # For SELECT queries, return list of dictionaries
    else:
        columns = [description[0] for description in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        conn.close()
        return results

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Query database for user's stocks
    stocks = execute_query(
        """
        SELECT symbol, SUM(shares) as total_shares
        FROM transactions
        WHERE user_id = ?
        GROUP BY symbol
        HAVING total_shares > 0
        """,
        session["user_id"]
    )

    # Get current price for each stock and calculate total value
    total_value = 0
    for stock in stocks:
        quote = lookup(stock["symbol"])
        stock["name"] = quote["name"]
        stock["price"] = quote["price"]
        stock["value"] = stock["price"] * stock["total_shares"]
        total_value += stock["value"]
    # Query database for user's cash
    rows = execute_query("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = rows[0]["cash"]

    # Calculate grand total
    grand_total = cash + total_value

    return render_template("index.html", stocks=stocks, cash=cash, total=grand_total)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            return apology("must provide symbol", 400)
        if not shares:
            return apology("must specify number of shares", 400)
        try:
            shares = int(shares)
            if shares <= 0:
                raise ValueError
        except ValueError:
            return apology("Share count is not a positive integer", 400)

        # Look up stock symbol
        current_quote = lookup(symbol)
        if not current_quote:
            return apology("Invalid symbol", 400)

        total_cost = current_quote["price"] * shares
        rows = execute_query("SELECT cash FROM users WHERE id = ?", session.get("user_id"))
        remaining_cash = rows[0]["cash"]
        if total_cost > remaining_cash:
            return apology("Not enough money for the purchase", 400)

        # INSERT transaction into the table
        execute_query(
            "INSERT INTO transactions (user_id, symbol, shares, price, type) VALUES (?, ?, ?, ?, 'buy')",
            session["user_id"],
            current_quote["symbol"],
            shares,
            current_quote["price"]
        )

        # Update user's remaining cash
        execute_query(
            "UPDATE users SET cash = ? WHERE id = ?",
            remaining_cash - total_cost,
            session["user_id"]
        )

        # Return to homepage
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Query database for user's transactions
    transactions = execute_query(
        """
        SELECT symbol, shares, price, timestamp, type
        FROM transactions
        WHERE user_id = ?
        ORDER BY timestamp DESC
        """,
        session["user_id"]
    )
    return render_template("history.html", transactions = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = execute_query(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("must provide stock symbol", 400)
        returned_quote = lookup(symbol)
        if not returned_quote:
            return apology("Incorrect symbol provided", 400)
        return render_template("quoted.html", name=returned_quote["name"], price=returned_quote["price"], symbol=returned_quote["symbol"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # ensuring that the user provides a username
        if not username:
            return apology("must provide username", 400)
        if not password:
            return apology("must provide password", 400)
        if not confirmation:
            return apology("must provide password confirmation", 400)
        if password != confirmation:
            return apology("password and confirmation password did not match", 400)
        try:
            new_user_id = execute_query("INSERT INTO users (username, hash) VALUES (?, ?)",
            username, generate_password_hash(password))
        except sqlite3.IntegrityError:
            return apology("Username already exists", 400)

        session["user_id"] = new_user_id
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Problems that can occure
    # Selling shares which you don't have
    # Selling more shares than you have
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            return apology("must provide symbol", 400)
        if not shares:
            return apology("must specify number of shares", 400)
        try:
            shares = int(shares)
            if shares <= 0:
                raise ValueError
        except ValueError:
            return apology("Share count is not a positive integer", 400)
        # Query database for user's shares of stock

        rows = execute_query(
            """
            SELECT SUM(shares) as total_shares
            FROM transactions
            WHERE user_id = ? AND symbol = ?
            GROUP BY symbol
            """,
            session["user_id"],
            request.form.get("symbol")
        )
        if not rows or (shares > rows[0]["total_shares"]):
            return apology ("Not enough shares to sell", 400)
        current_quote = lookup(symbol)
        execute_query(
            "INSERT INTO transactions (user_id, symbol, shares, price, type) VALUES (?, ?, ?, ?, 'sell')",
            session["user_id"],
            current_quote["symbol"],
            -shares,
            current_quote["price"]
        )
        if not current_quote:
            return apology("Invalid symbol", 400)

        total_cost = current_quote["price"] * shares

        # Update user's remaining cash
        execute_query(
            "UPDATE users SET cash = cash + ? WHERE id = ?",
            total_cost,
            session["user_id"]
        )
        return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        # Get list of symbols user owns
        stocks = execute_query(
            """
            SELECT symbol
            FROM transactions
            WHERE user_id = ?
            GROUP BY symbol
            HAVING SUM(shares) > 0
            """,
            session["user_id"]
        )
        return render_template("sell.html", stocks=stocks)

@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """User can add cash"""
    if request.method == "POST":

        newly_added_cash = (request.form.get("new_cash"))

        if not newly_added_cash:
            return apology("Invalid cash amount", 400)

        try:
            newly_added_cash = int(newly_added_cash)
            if newly_added_cash <= 0 or newly_added_cash > 100000:
                raise ValueError
        except ValueError:
            return apology("Money added should be positive and less than 100,000", 400)


        user_id = session["user_id"]
        user_cash = execute_query("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash[0]["cash"]
        updated_cash = user_cash + newly_added_cash

        execute_query("UPDATE users SET cash = ? WHERE id = ?", updated_cash, user_id)
        return redirect("/")

    else:
        return render_template("addcash.html")

if __name__ == '__main__':
    app.run(debug=True)