
import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # query all relevant stocks
    stocks = db.execute("SELECT symbol, SUM(quantity) as quantity FROM history WHERE user_id=:user_id GROUP BY symbol", user_id=session["user_id"])
    # query current cash
    result = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    cash = float(result[0]['cash'])
    grand_total = 0
    for stock in stocks:
        quote = lookup(stock['symbol'])
        stock['current_price'] = float(quote['price'])
        stock['current_value'] = float(stock['quantity']* stock['current_price'])
        grand_total += stock['current_value']
        stock['current_price'] = usd(stock['current_price'])
        stock['current_value'] = usd(stock['current_value'])
    grand_total += cash
    grand_total = usd(grand_total)
    return render_template("index.html", stocks=stocks, grand_total = grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # if stock not found:
        if request.form.get("stocksymbol") == None:
            return apology("Stock not found", 403)
        cash = db.execute("select cash from users where id=:id", id=session["user_id"])
        quote = lookup(request.form.get("stocksymbol"))
        # check if enough cash:
        if quote["price"]*int(request.form.get("quantity")) > cash[0]["cash"]:
            return apology("Not enough cash", 403)
        else:
            db.execute("UPDATE users SET cash = cash - :sum where id = :id", sum=quote["price"]*int(request.form.get("quantity")), id = session["user_id"])

        # update transaction history:
        db.execute("INSERT INTO history (user_id, symbol, price, quantity, datetime) VALUES (:user_id, :symbol, :price, :quantity, :datetime)",
        user_id=session['user_id'], symbol = quote['symbol'], price = quote['price'], quantity = int(request.form.get("quantity")), datetime = datetime.datetime.now())

    return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    username = request.args.get("username")
    rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.args.get("username"))
    if len(rows)!=0:
        return jsonify("false")
    return jsonify("true")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    stocks = db.execute("SELECT * FROM history WHERE user_id = :user_id", user_id=session["user_id"])
    for stock in stocks:
        if stock['quantity']<0:
            stock['buysell'] = "Sell"
            stock['quantity'] = stock['quantity']*(-1)
        else:
            stock['buysell'] = "Buy"

    return render_template("history.html", stocks = stocks)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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
        quote = lookup(request.form.get("quote"))
        if quote == None:
            return apology("Stock not found", 403)
    else:
        return render_template("quote.html")
    return render_template("quote1.html", quote=quote)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

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

        # Ensure password confirmation was submitted
        elif not request.form.get("password2"):
            return apology("must provide password confirmation", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # ensure both passwords match:
        if request.form.get("password") != request.form.get("password2"):
            return apology("password must match", 403)

        # hash the password
        hash = generate_password_hash(request.form.get("password"))

        # insert newuser details:
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash = hash)

        rows = db.execute("SELECT * FROM users WHERE username = :username",
            username=request.form.get("username"))

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # prepare all stocks:
    stocks = db.execute("SELECT symbol, SUM(quantity) as quantity FROM history WHERE user_id=:user_id GROUP BY symbol", user_id=session["user_id"])
    # find exceptions:
    if request.method == "POST":
        # if stock not found:
        if request.form.get("stocksymbol") == None:
            return apology("Stock not found", 403)
        if request.form.get("quantity") == "":
            return apology("Please enter a quantity", 403)

        qty=0
        for stock in stocks:
            if stock['symbol'] == request.form.get("stocksymbol").upper():
                qty = stock['quantity']
        if qty ==0:
            return apology("Stock not found", 403)
        elif int(request.form.get("quantity")) > qty:
            return apology("Not enough shares to sell")

        quote = lookup(request.form.get("stocksymbol", 403))

        # update transaction history:
        db.execute("INSERT INTO history (user_id, symbol, price, quantity, datetime) VALUES (:user_id, :symbol, :price, :quantity, :datetime)",
        user_id=session['user_id'], symbol = quote['symbol'], price = quote['price'], quantity = int(float(request.form.get("quantity"))*(-1)), datetime = datetime.datetime.now())
        db.execute("UPDATE users SET cash = cash + :sum where id = :id", sum=quote["price"]*int(request.form.get("quantity")), id = session["user_id"])

    return render_template("sell.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

# change password:
@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    result = db.execute("select * from users where id=:id", id=session["user_id"])
    username = result[0]['username']
    if request.method=="POST":
        if not check_password_hash(result[0]["hash"], request.form.get("password")):
            return apology("invalid password", 403)
        elif (request.form.get("new_password")!=request.form.get("new_password2")):
            return apology("new password must match")
        hash = generate_password_hash(request.form.get("new_password"))
        # update password:
        db.execute("UPDATE users SET hash = :hash where id = :id", id = session["user_id"], hash = hash)
        return redirect("/")
    else:
        return render_template("change_password.html", username=username)
