from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3, os, random, string
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "change_this_password"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# --- Initialisation base de données ---
def init_db():
    conn = sqlite3.connect("shop.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS articles (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 nom TEXT,
                 prix REAL,
                 description TEXT,
                 image TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS commandes (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 code TEXT,
                 contenu TEXT,
                 total REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
                 id INTEGER PRIMARY KEY,
                 primary_color TEXT,
                 secondary_color TEXT)""")
    c.execute("INSERT OR IGNORE INTO settings (id, primary_color, secondary_color) VALUES (1, '#e0112b', '#111111')")
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect("shop.db")

def generer_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# --- Config admin ---
ADMIN_USER = "admin"
ADMIN_PASS = "password"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("login"))

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = get_db()
    c = conn.cursor()
    commande = None

    if request.method == "POST":
        if "ajouter" in request.form:
            nom = request.form["nom"]
            try:
                prix = float(request.form["prix"])
            except ValueError:
                prix = 0.0
            description = request.form["description"]
            image = request.files["image"]
            image_filename = None
            if image and image.filename != "":
                image_filename = secure_filename(image.filename)
                image.save(os.path.join(app.config["UPLOAD_FOLDER"], image_filename))
            c.execute("INSERT INTO articles (nom, prix, description, image) VALUES (?, ?, ?, ?)",
                      (nom, prix, description, image_filename))

        elif "supprimer" in request.form:
            id_article = request.form["supprimer"]
            c.execute("DELETE FROM articles WHERE id=?", (id_article,))

        elif "chercher" in request.form:
            code = request.form["code"].strip().upper()
            c.execute("SELECT * FROM commandes WHERE code=?", (code,))
            commande = c.fetchone()

        elif "changer_couleurs" in request.form:
            primary = request.form["primary_color"]
            secondary = request.form["secondary_color"]
            c.execute("UPDATE settings SET primary_color=?, secondary_color=? WHERE id=1",
                      (primary, secondary))

        conn.commit()

    c.execute("SELECT * FROM articles")
    articles = c.fetchall()
    c.execute("SELECT primary_color, secondary_color FROM settings WHERE id=1")
    colors = c.fetchone()
    conn.close()
    return render_template("admin.html", articles=articles, commande=commande, colors=colors)

@app.route("/")
def shop():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM articles")
    articles = c.fetchall()
    c.execute("SELECT primary_color, secondary_color FROM settings WHERE id=1")
    colors = c.fetchone()
    conn.close()
    return render_template("shop.html", articles=articles, colors=colors)

@app.route("/produit/<int:article_id>")
def produit(article_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM articles WHERE id=?", (article_id,))
    article = c.fetchone()
    c.execute("SELECT primary_color, secondary_color FROM settings WHERE id=1")
    colors = c.fetchone()
    conn.close()
    return render_template("produit.html", article=article, colors=colors)

@app.route("/ajouter_panier/<int:article_id>")
def ajouter_panier(article_id):
    panier = session.get("panier", [])
    panier.append(article_id)
    session["panier"] = panier
    return redirect(url_for("shop"))

@app.route("/panier", methods=["GET", "POST"])
def panier():
    conn = get_db()
    c = conn.cursor()
    panier = session.get("panier", [])
    items, total = [], 0

    for art_id in panier:
        c.execute("SELECT * FROM articles WHERE id=?", (art_id,))
        art = c.fetchone()
        if art:
            items.append(art)
            total += art[2]

    if request.method == "POST" and items:
        code = generer_code()
        contenu = ", ".join([i[1] for i in items])
        c.execute("INSERT INTO commandes (code, contenu, total) VALUES (?, ?, ?)", (code, contenu, total))
        conn.commit()
        conn.close()
        session.pop("panier", None)
        return render_template("confirmation.html", code=code, total=total)

    conn.close()
    return render_template("panier.html", items=items, total=total)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

