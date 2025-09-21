import os, sqlite3, random, string
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "exn_secret_key"
DB_NAME = "shop.db"
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_USER = "getpost"
ADMIN_PASS = "tonght67"

# ---------- DB ----------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS produits(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        prix REAL NOT NULL,
        description TEXT,
        image TEXT,
        categorie_id INTEGER,
        FOREIGN KEY(categorie_id) REFERENCES categories(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS commandes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        items TEXT NOT NULL,
        total REAL NOT NULL,
        email TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

# ---------- Contexte (menu) ----------
@app.context_processor
def inject_categories():
    try:
        conn = get_db()
        cats = conn.execute("SELECT id, nom FROM categories ORDER BY nom ASC").fetchall()
        conn.close()
    except Exception:
        cats = []
    return dict(nav_categories=cats)

# ---------- Pages publiques ----------
@app.route("/")
def index():
    conn = get_db()
    produits = conn.execute("SELECT * FROM produits ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("index.html", produits=produits)

@app.route("/categorie/<int:cat_id>")
def categorie(cat_id):
    conn = get_db()
    cat = conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    produits = conn.execute("SELECT * FROM produits WHERE categorie_id=? ORDER BY id DESC", (cat_id,)).fetchall()
    conn.close()
    return render_template("categorie.html", categorie=cat, produits=produits)

@app.route("/produit/<int:prod_id>")
def produit(prod_id):
    conn = get_db()
    p = conn.execute("SELECT * FROM produits WHERE id=?", (prod_id,)).fetchone()
    conn.close()
    if not p:
        return redirect(url_for("index"))
    return render_template("produit.html", produit=p)

# ---------- Panier ----------
@app.route("/ajouter_panier/<int:prod_id>", methods=["GET","POST"])
def ajouter_panier(prod_id):
    session.setdefault("panier", [])
    session["panier"].append(prod_id)
    session.modified = True
    return redirect(url_for("panier"))

@app.route("/supprimer_panier/<int:prod_id>")
def supprimer_panier(prod_id):
    session.setdefault("panier", [])
    session["panier"] = [pid for pid in session["panier"] if pid != prod_id]
    session.modified = True
    return redirect(url_for("panier"))

@app.route("/vider_panier")
def vider_panier():
    session["panier"] = []
    session.modified = True
    return redirect(url_for("panier"))

@app.route("/panier")
def panier():
    panier_ids = session.get("panier", [])
    conn = get_db()
    produits, total = [], 0.0
    for pid in panier_ids:
        p = conn.execute("SELECT * FROM produits WHERE id=?", (pid,)).fetchone()
        if p:
            produits.append(p)
            total += float(p["prix"])
    conn.close()
    return render_template("panier.html", produits=produits, total=total)

@app.route("/valider_commande", methods=["POST"])
def valider_commande():
    panier_ids = session.get("panier", [])
    if not panier_ids:
        return redirect(url_for("panier"))
    email = request.form.get("email","")
    conn = get_db()
    items, total = [], 0.0
    for pid in panier_ids:
        p = conn.execute("SELECT * FROM produits WHERE id=?", (pid,)).fetchone()
        if p:
            items.append(f"{p['nom']} ({p['prix']})")
            total += float(p["prix"])
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    conn.execute("INSERT INTO commandes (code, items, total, email) VALUES (?, ?, ?, ?)", (code, ", ".join(items), total, email))
    conn.commit()
    conn.close()
    session["panier"] = []
    return render_template("commande.html", code=code, items=items, total=total)

# ---------- Connexion / Admin ----------
@app.route("/connexion", methods=["GET","POST"])
def connexion():
    if request.method == "POST":
        user = request.form.get("username","")
        pwd  = request.form.get("password","")
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin"))
        return render_template("connexion.html", error="Identifiants incorrects")
    return render_template("connexion.html")

@app.route("/deconnexion")
def deconnexion():
    session.pop("admin", None)
    return redirect(url_for("index"))

def require_admin():
    return bool(session.get("admin"))

@app.route("/admin")
def admin():
    if not require_admin():
        return redirect(url_for("connexion"))
    conn = get_db()
    categories = conn.execute("SELECT * FROM categories ORDER BY nom ASC").fetchall()
    produits   = conn.execute("SELECT * FROM produits ORDER BY id DESC").fetchall()
    commandes  = conn.execute("SELECT * FROM commandes ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin.html", categories=categories, produits=produits, commandes=commandes)

# ---- CatÃ©gories
@app.route("/admin/ajouter_categorie", methods=["POST"])
def ajouter_categorie():
    if not require_admin(): return redirect(url_for("connexion"))
    nom = request.form.get("nom","").strip()
    if nom:
        conn = get_db()
        conn.execute("INSERT INTO categories (nom) VALUES (?)", (nom,))
        conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/supprimer_categorie/<int:cat_id>")
def supprimer_categorie(cat_id):
    if not require_admin(): return redirect(url_for("connexion"))
    conn = get_db()
    conn.execute("UPDATE produits SET categorie_id=NULL WHERE categorie_id=?", (cat_id,))
    conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

# ---- Produits
def _save_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    safe = os.path.basename(file_storage.filename)
    ext = os.path.splitext(safe)[1]  # garde l extension d origine (jpg/png/webp/gif, etc.)
    unique = uuid4().hex + ext
    path = os.path.join(UPLOAD_FOLDER, unique)
    file_storage.save(path)
    return f"uploads/{unique}"

@app.route("/admin/ajouter_produit", methods=["POST"])
def admin_ajouter_produit():
    if not require_admin(): return redirect(url_for("connexion"))
    nom = request.form.get("nom","").strip()
    prix = float(request.form.get("prix","0") or 0)
    description = request.form.get("description","").strip()
    categorie_id = request.form.get("categorie_id") or None
    image = _save_image(request.files.get("image"))
    conn = get_db()
    conn.execute("""INSERT INTO produits (nom, prix, description, image, categorie_id)
                    VALUES (?, ?, ?, ?, ?)""", (nom, prix, description, image, categorie_id))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/modifier_produit/<int:prod_id>", methods=["GET","POST"])
def admin_modifier_produit(prod_id):
    if not require_admin(): return redirect(url_for("connexion"))
    conn = get_db()
    if request.method == "POST":
        nom = request.form.get("nom","").strip()
        prix = float(request.form.get("prix","0") or 0)
        description = request.form.get("description","").strip()
        categorie_id = request.form.get("categorie_id") or None
        image_exist = request.form.get("image_exist") or None
        image_new = _save_image(request.files.get("image"))
        image = image_new if image_new else image_exist
        conn.execute("""UPDATE produits SET nom=?, prix=?, description=?, image=?, categorie_id=? WHERE id=?""",
                     (nom, prix, description, image, categorie_id, prod_id))
        conn.commit(); conn.close()
        return redirect(url_for("admin"))
    p = conn.execute("SELECT * FROM produits WHERE id=?", (prod_id,)).fetchone()
    categories = conn.execute("SELECT * FROM categories ORDER BY nom ASC").fetchall()
    conn.close()
    return render_template("modifier_produit.html", produit=p, categories=categories)

@app.route("/admin/supprimer_produit/<int:prod_id>")
def admin_supprimer_produit(prod_id):
    if not require_admin(): return redirect(url_for("connexion"))
    conn = get_db()
    conn.execute("DELETE FROM produits WHERE id=?", (prod_id,))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

# ---- Commandes
@app.route("/admin/rechercher_commande", methods=["POST"])
def rechercher_commande():
    if not require_admin(): return redirect(url_for("connexion"))
    code = (request.form.get("code","") or "").upper()
    conn = get_db()
    cmd = conn.execute("SELECT * FROM commandes WHERE code=?", (code,)).fetchone()
    conn.close()
    if cmd:
        return render_template("commande.html", code=cmd["code"], items=cmd["items"].split(", "), total=cmd["total"])
    return render_template("commande.html", code=None, items=[], total=0)

if __name__ == "__main__":
    app.run(debug=True)
