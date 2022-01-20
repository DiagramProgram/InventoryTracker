import os
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, make_response
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import csv
from io import StringIO
from datetime import datetime
from werkzeug.wrappers import Response

from helpers import apology, login_required, usd

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
    """Show product inventory"""

    user = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

    info = db.execute("SELECT symbol, share_name, shares_num, shares_price FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])

    # How much cash the user has in their account
    cash = user[0]["cash"]

    total = 0

    for each in info:
        symbol = each["symbol"]
        shares = each["shares_num"]
        shares_price = each["shares_price"]

        total += shares * shares_price


    return render_template("index.html", cash=cash, info=info, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        # Name, price, symbol
        company = request.form.get("company")
        book = request.form.get("name")
        price = float(request.form.get("price"))
        shares_num = int(request.form.get("quantity"))

        # Ensure nothing is left blank or that symbol is invalid
        if not request.form.get("name"):
            return apology("please enter a product name", "Sorry!")

        elif not request.form.get("price") or price <= 0:
            return apology("must provide valid price", "Sorry!")

        elif not request.form.get("quantity") or shares_num <= 0:
            return apology("must provide valid product quantity", "Sorry!")

        elif not request.form.get("company"):
            return apology("please input the company you bought the product from", "Sorry!")

        # Query database for cash in account for current user
        rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

        cashamt = rows[0]["cash"]

        purchaseamt = price*shares_num

        if purchaseamt > cashamt:
            return apology("not enough money to complete transaction", "Sorry!")

        # Update cash after purchase
        db.execute("UPDATE users SET cash = cash - :purchaseamt WHERE id = :user_id", purchaseamt=purchaseamt, user_id=session["user_id"])

        # Check if it already exists in the database, and if so, simply update it instead of creating a new entry
        info = db.execute("SELECT shares_num, shares_price FROM transactions WHERE user_id = :user_id AND symbol = :symbol",
                           user_id=session["user_id"], symbol=book.lower())

        if len(info) != 0:
            db.execute("UPDATE transactions SET shares_num = shares_num + :new_amt, shares_price = ((shares_price*shares_num) + (:added_price*:new_amt))/(shares_num+:new_amt) WHERE user_id = :user_id AND symbol = :symbol",
                        new_amt = shares_num, added_price = book['price'],
                        user_id=session["user_id"], symbol=book.lower())

        else:
            # Make new table and update its database with purchasing info
            #print(info)
            db.execute("INSERT INTO transactions (user_id, share_name, symbol, shares_num, shares_price) VALUES (:user_id, :share_name, :symbol, :shares_num, :shares_price)",
                       user_id=session["user_id"],
                       share_name=company,
                       symbol=book,
                       shares_num=shares_num,
                       shares_price=price)


        # Table solely for containing information needed to show transaction history
        db.execute("INSERT INTO transhist (user_id, symbol, shares_num, shares_price) VALUES (:user_id, :symbol, :shares_num, :shares_price)",
                   user_id=session["user_id"],
                   symbol=book,
                   shares_num=shares_num,
                   shares_price=price)

        flash("Successfully Bought!")

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    info = db.execute("SELECT * FROM transhist WHERE user_id = :user_id", user_id=session["user_id"])

    return render_template("history.html", info=info)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", "Sorry!")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", "Sorry!")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", "Sorry!")

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


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    #if submitted
    if request.method == "POST":

        # Ensure username is provided
        if not request.form.get("username"):
            return apology("must provide a username", "Sorry!")

        # Ensure password is provided
        elif not request.form.get("password"):
            return apology("must provide a password", "Sorry!")

        # Ensure password confirmation is provided
        elif not request.form.get("password"):
            return apology("must provide a password retype", "Sorry!")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Check if username already exists
        if len(rows) == 1:
            return apology("username already exists", "Sorry!")

        # Check if pasword retype matches initial password
        elif request.form.get("confirmation") != request.form.get("password"):
            return apology("passwords don't match", "Sorry!")

        # Check if password length is at least 6 or more characters
        elif len(request.form.get("password")) < 5:
            return apology("password must be at least 6 characters", "Sorry!")

        # If its good, we may proceed
        else:
            newp = generate_password_hash(request.form.get("password"))

            db.execute("INSERT INTO users (username, hash) VALUES (:user, :newp)", user=request.form.get("username"), newp=newp)

            return redirect("/login")

    else:
        return render_template("register.html")


@app.route('/export', methods=['GET'])
@login_required
def download_log():
    def generate():
        data = StringIO()
        w = csv.writer(data)

        # write header
        w.writerow(('company', 'product name', 'quantity', 'price'))
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)

        all = db.execute("SELECT * FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])
        # all = db.execute("SELECT * FROM transactions")
        print(all)

        for each in all:
            list = []
            for key in each:
                list.append(each[key])
            # print(list)
            w.writerow((
                list[1],
                list[2],
                list[3],
                list[4]))
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)

    # stream the response as the data is generated
    response = Response(generate(), mimetype='text/csv')
    # add a filename
    response.headers.set("Content-Disposition", "attachment", filename="log.csv")
    return response


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        book = request.form.get("sel1")

        my_symb = book #.lower()

        fut = db.execute("SELECT shares_num from transactions WHERE user_id = :user_id AND symbol = :symbol", # GIVES [{'shares_num': 4}]
                         user_id=session["user_id"],
                         symbol=my_symb)

        # Original amount of shares in account
        bla = fut[0]['shares_num']

        # Query database for cash in account for current user
        rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

        cashamt = rows[0]["cash"]

        shares_sold_num = int(request.form.get("shares"))

        getprice = db.execute("SELECT 	shares_price from transactions WHERE user_id = :user_id AND symbol = :symbol", # GIVES [{'shares_price': 4.59}]
                         user_id=session["user_id"],
                         symbol=my_symb)

        price = float(getprice[0]['shares_price'])

        saleamt = price*shares_sold_num


        # ----------- a few if statements -----------

        # Ensure nothing is left blank or that symbol is invalid
        if not request.form.get("sel1"):
            return apology("please select a share to sell", "Sorry!")

        elif not request.form.get("shares") or shares_sold_num <= 0:
            return apology("must provide valid number of shares", "Sorry!")

        elif shares_sold_num > bla:
            return apology("not enough shares in portfolio", "Sorry!")


        # Original amount - amount sold
        updatednum = bla-shares_sold_num

        if updatednum > 0:
            # Update portfolio table on hompeage
            db.execute("UPDATE transactions SET shares_num = :updatednum WHERE user_id = :user_id AND symbol = :symbol", updatednum=updatednum, user_id=session["user_id"], symbol=my_symb)

        # If the user sold all of their shares for that stock
        else:
            db.execute("DELETE FROM transactions WHERE user_id = :user_id AND symbol = :symbol", user_id=session["user_id"], symbol=my_symb)
            #db.execute("UPDATE transactions SET shares_num = :updatednum WHERE user_id = :user_id AND symbol = :symbol", updatednum=updatednum, user_id=session["user_id"], symbol=my_symb)

        # Update cash after purchase
        db.execute("UPDATE users SET cash = cash + :saleamt WHERE id = :user_id", saleamt=saleamt, user_id=session["user_id"])

        # Table solely for containing information needed to show transaction history
        db.execute("INSERT INTO transhist (user_id, symbol, shares_num, shares_price) VALUES (:user_id, :symbol, :shares_num, :shares_price)",
                   user_id=session["user_id"],
                   symbol=my_symb,
                   shares_num=-shares_sold_num,
                   shares_price=price)

        flash("Sold!")

        return redirect("/")

    else:
        # To display list of all current stocks
        transinfo = db.execute("SELECT * FROM transactions WHERE user_id = :user_id",
                          user_id=session["user_id"])

        return render_template("sell.html", transinfo=transinfo)


def errorhandler(e):
    """Handle errors"""

    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
