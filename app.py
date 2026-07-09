import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session, flash, url_for, g, Response
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import  datetime
import calendar
import csv
import io

load_dotenv()  # This loads the variables from the .env file
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

def get_db():
    conn = sqlite3.connect("subscriptions.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        hash_pw = generate_password_hash(password)

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hash_pw))
            conn.commit()
            flash("Registration Successful! Please login.", "success")
            return redirect("/login")
        except sqlite3.IntegrityError:
            flash("Email already registered.", "danger")
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect("/")
        else:
            flash("Invalid email or password", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/",methods=["GET","POST"])
def home():
    #Bounce users not logged in
    if not session.get("user_id"):
        return redirect("/login")
    conn=get_db()
    cur=conn.cursor()

    #Save New Data
    if request.method=="POST":
        new_name=request.form.get("name")
        new_price=float(request.form.get("price"))
        new_due=request.form.get("due_date")
        new_category=request.form.get("category")
        new_cycle=request.form.get("billing_cycle")
        cur_user=session.get("user_id")
        cur.execute('''
            INSERT INTO subscriptions (name,price,due_date,category,user_id,billing_cycle) VALUES (?,?,?,?,?,?)
        ''',(new_name,new_price,new_due,new_category,cur_user,new_cycle))
        conn.commit()
        conn.close()
        return redirect("/")

    #Read All Data
    cur_user = session.get("user_id")
    conn=get_db()
    cur=conn.cursor()
    sort_by=request.args.get("sort","due_date")
    sort_dir=request.args.get("dir","asc").upper()
    if sort_by not in ["name","price","due_date"]:
        sort_by="due_date"
    if sort_dir not in ["ASC","DESC"]:
        sort_dir="ASC"
    cur.execute(f"SELECT * FROM subscriptions WHERE user_id=? ORDER BY {sort_by} {sort_dir}",(cur_user,))
    subs=cur.fetchall()
    cur.execute("SELECT category, SUM(price) as total_cost FROM subscriptions WHERE user_id=? GROUP BY category",(cur_user,))
    cats=cur.fetchall()

    #Total cost & Alerts
    tod=datetime.date.today()
    tot=0.0
    alerts=[]
    act_subs=[]
    exp_subs=[]
    for i in subs:
        due = datetime.datetime.strptime(i["due_date"], "%Y-%m-%d").date()
        left=(due-tod).days
        #billing cycle
        i_dict=dict(i)
        cycle=i_dict.get("billing_cycle","Monthly")
        #Auto-renew
        if left<0 and cycle!="one-Time":
            if cycle=="Monthly":
                due+=datetime.timedelta(days=30)
            elif cycle=="Yearly":
                due+=datetime.timedelta(days=365)
            cur.execute("UPDATE subscriptions SET due_date=? WHERE id=?",(due.strftime("%Y-%m-%d"),i["id"]))
            conn.commit()
            left=(due-tod).days
            i_dict["due_date"]=due.strftime("%Y-%m-%d")
        if left<0:
            exp_subs.append(i_dict)
        else:
            act_subs.append(i_dict)
            if cycle=="Monthly":
                tot += float(i_dict["price"])
            elif cycle=="Yearly":
                tot+=float(i_dict["price"])/12.0
            if left<=7:
                alerts.append(i_dict["name"])
    tot=round(tot,2)
    #Dynamic spend trend
    td=[0.0]*6
    ml=[]
    for m in range(6):
        mn=(tod.month+m-1)%12+1
        ml.append(calendar.month_abbr[mn])
    for sub in act_subs:
        price=float(sub["price"])
        cycle=sub.get("billing_cycle","Monthly")
        due=datetime.datetime.strptime(sub["due_date"], "%Y-%m-%d").date()
        for m in range(6):
            tm=(tod.month+m-1)%12+1
            if cycle=="Monthly":
                td[m]+=price
            elif cycle=="Yearly" and due.month==tm:
                td[m]+=price
            elif cycle=="One-Time" and due.month==tm and due.year==tod.year:
                td[m]+=price
    conn.close()
    return render_template("index.html",tot=tot,alerts=alerts,subs=act_subs,exp_subs=exp_subs,category_totals=cats,trend_data=td,month_labels=ml)


@app.route('/export')
def export_csv():
    # 1. Get the data from the database
    conn=get_db()
    cur=conn.cursor()
    cur.execute("SELECT name, price, due_date, billing_cycle, category FROM subscriptions")
    subs=cur.fetchall()

    # 2. Create an in-memory text stream to hold the CSV data
    output = io.StringIO()
    writer = csv.writer(output)

    # 3. Write the header row
    writer.writerow(['Name', 'Price ($)', 'Due Date', 'Billing Cycle', 'Category'])

    # 4. Write all the subscription rows
    for sub in subs:
        writer.writerow([sub['name'], sub['price'], sub['due_date'], sub['billing_cycle'], sub['category']])

    # 5. Create the response and tell the browser it's a downloadable CSV file
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=subscriptions_backup.csv'
    return response

@app.route("/delete",methods=["POST"])
def del_sub():
    sub_del=request.form.get("sub_id")
    cur_user=session.get("user_id")
    if not cur_user:
        return redirect("/login")
    conn =get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM subscriptions WHERE id=? AND user_id=?",(sub_del,cur_user))
    conn.commit()
    conn.close()
    return redirect("/")
@app.route("/edit/<int:id>",methods=["GET","POST"])
def edit_sub(id):
    conn=get_db()
    cur_user=session.get("user_id")
    if not cur_user:
        return redirect("/login")
    cur=conn.cursor()
    if request.method=="POST":
        cur.execute('''
            UPDATE subscriptions SET name=?,price=?,due_date=? WHERE id=? AND user_id=?
        ''',(request.form.get("name"),request.form.get("price"),request.form.get("due_date"),id,cur_user))
        conn.commit()
        conn.close()
        return redirect("/")
    cur.execute("SELECT * FROM subscriptions WHERE id=? AND user_id=?",(id,cur_user))
    sub=cur.fetchone()
    conn.close()
    if not sub:
        return redirect("/")
    return render_template("edit.html",sub=sub)

@app.route("/change-password", methods=["POST"])
def change_password():
    cur_user = session.get("user_id")
    if not cur_user:
        return redirect("/login")

    current_password = request.form.get("current_pwd")
    new_password = request.form.get("new_pwd")

    conn = get_db()
    cur = conn.cursor()

    # Get current user data
    cur.execute("SELECT * FROM users WHERE id = ?", (cur_user,))
    user = cur.fetchone()

    # Verify old password
    if user and check_password_hash(user["password"], current_password):
        new_hash = generate_password_hash(new_password)

        # 💾 The SQL UPDATE command:
        cur.execute("UPDATE users SET password = ? WHERE id = ?", (new_hash, cur_user))

        conn.commit()
        flash("Password updated successfully!", "success")
    else:
        flash("Incorrect current password.", "danger")

    conn.close()
    return redirect("/")

if __name__=="__main__":
    app.run(debug=True)

