import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

from datetime import datetime, timezone


app = Flask(__name__)


app.config["TEMPLATES_AUTO_RELOAD"] = True

@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


app.jinja_env.filters["usd"] = usd


app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


db = SQL("sqlite:///finance.db")



@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    user_id = session["user_id"]
    user_stock_info = db.execute(
        "SELECT symbol, name, SUM(shares) as total_shares, price FROM purchase WHERE user_id = ? GROUP BY symbol", user_id)

    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

    total = user_cash
    for stock in user_stock_info:
        total += stock["price"] * stock["total_shares"]

    return render_template("index.html", user_stock_info=user_stock_info, user_cash=usd(user_cash),
                           total=usd(total), usd=usd, lookup=lookup, percentage=percentage)


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """Add Cash"""

    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    if request.method == "GET":
        return render_template("add_cash.html", user_cash=usd(user_cash))

    added_cash = request.form.get("added_cash")
    new_total_cash = float(added_cash) + float(user_cash)
    db.execute("UPDATE users SET cash = ? WHERE id = ?", new_total_cash, session["user_id"])
    db.execute("INSERT INTO purchase(user_id, type, symbol, name, shares, price) VALUES(?, ?, ?, ?, ?, ?)",
                   session["user_id"], "ADD CASH", "N/A", "N/A", 1, float(added_cash))

    return render_template("add_cash.html",user_cash=usd(new_total_cash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "GET":
        temp = request.args.get("buy_symbol")
        if not temp:
            buy_symbol = ""
        else:
            buy_symbol = temp
        return render_template("buy.html", buy_symbol=buy_symbol)

    stock_info = lookup(request.form.get("symbol"))

    try:
        number = int(request.form.get("shares"))
    except ValueError:
        return apology("Shares should be positive integer")


    if not stock_info:
        return apology("Invalid symbol or This symbol does not exist")

    if number <= 0:
        return apology("Shares should be positive integer")


    stock_symbol = stock_info["symbol"]
    stock_name = stock_info["name"]
    stock_price = stock_info["price"]

    user_id = session["user_id"]


    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

    remaining_cash = user_cash - (stock_price * number)

    if remaining_cash < 0:
        return apology("You do not have enough cash to buy the stocks")


    else:
        db.execute("UPDATE users SET cash = ? WHERE id = ?", remaining_cash, user_id)
        db.execute("INSERT INTO purchase(user_id, type, symbol, name, shares, price) VALUES(?, ?, ?, ?, ?, ?)",
                   user_id, "BUY", stock_symbol, stock_name, number, stock_price)
        return redirect("/")


@app.route("/changepassword", methods=["GET", "POST"])
def change_password():
    """Allow user to change their password"""

    if request.method == "GET":
        return render_template("changepassword.html")


    current_pw = request.form.get("current_password")
    new_pw = request.form.get("new_password")
    confirm_new_pw = request.form.get("confirm_new_password")


    if not current_pw:
        return apology("You should input your current password")


    old_password = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])
    if len(old_password) != 1 or not check_password_hash(old_password[0]["hash"], current_pw):
        return apology("invalid username and/or password", 403)

    if not new_pw:
        return apology("You should input your new password")
    elif not confirm_new_pw:
        return apology("You should input your password in 'Confirmation New Password'")
    elif new_pw != confirm_new_pw:
        return apology("Password does not match")


    hashed_new_pw = generate_password_hash(new_pw)
    db.execute("UPDATE users SET hash = ? WHERE id = ?", hashed_new_pw, session["user_id"])

    return redirect("/logout")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""


    transaction_info = db.execute(
        "SELECT type, symbol, price, shares, timestamp FROM purchase WHERE user_id = ? ORDER BY timestamp DESC", session["user_id"])
    return render_template("history.html", transaction_info=transaction_info, usd=usd)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""


    session.clear()

    if request.method == "POST":


        if not request.form.get("username"):
            return apology("must provide username", 403)


        elif not request.form.get("password"):
            return apology("must provide password", 403)

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))


        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)


        session["user_id"] = rows[0]["id"]

        return redirect("/")


    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

 
    session.clear()

    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""


    if request.method == "GET":
        return render_template("quote.html")


    stock_info = lookup(request.form.get("symbol"))
    if not stock_info:
        return apology("Invalid symbol or This symbol does not exist")

    return render_template("quoted.html", name=stock_info["name"], price=usd(stock_info["price"]),
                           symbol=stock_info["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""


    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username")
    pw = request.form.get("password")
    confirm_pw = request.form.get("confirmation")

    if not username:
        return apology("You should input the username")
    elif not pw:
        return apology("You should input your password")
    elif not confirm_pw:
        return apology("You should input your password in 'Confirmation Password'")
    elif pw != confirm_pw:
        return apology("Password does not match")


    hashed_pw = generate_password_hash(pw)

 
    try:
        db.execute("INSERT INTO users(username, hash) VALUES(?, ?)", username, hashed_pw)

    except:
        return apology("Username registered by others already")


    return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    user_id = session["user_id"]

 
    if request.method == "GET":


        temp = request.args.get("sell_symbol")
        if not temp:
            sell_symbol = ""
        else:
            sell_symbol = temp


        stock_symbol = db.execute("SELECT symbol FROM purchase WHERE user_id = ? GROUP BY symbol", user_id)

        return render_template("sell.html", stock_symbol=stock_symbol, sell_symbol=sell_symbol)


    else:

        selected_stock_symbol = request.form.get("symbol")
        number = int(request.form.get("shares"))

        selected_stock_price = lookup(selected_stock_symbol)["price"]
        selected_stock_name = lookup(selected_stock_symbol)["name"]

        if number <= 0:
            return apology("Shares should be positive integer")


        current_own_shares = db.execute("SELECT SUM(shares) as total_shares FROM purchase WHERE user_id = ? AND symbol = ? GROUP BY symbol",
                                        user_id, selected_stock_symbol)[0]["total_shares"]

        if current_own_shares < number:
            return apology("You don't have enough shares to sell")


        current_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]


        db.execute("UPDATE users SET cash = ? WHERE id =?", (current_cash + (number * selected_stock_price)), user_id)


        db.execute("INSERT INTO purchase(user_id, type, symbol, name, shares, price) VALUES(?, ?, ?, ?, ?, ?)",
                   user_id, "SELL", selected_stock_symbol, selected_stock_name, -number, selected_stock_price)

        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)



for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


def percentage(value):
    """Format value as percentage. """
    return f"{value:,.2f}%"

