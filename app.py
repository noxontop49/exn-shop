import os
import random, string
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecret")

# ---------- DB CONFIG (SQLite en local / PostgreSQL en ligne) ----------
db_url = os.environ.get("DATABASE_URL", "sqlite:///shop.db")
# compatibilité Heroku/Render: postgres:// -> postgresql+psycopg2://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Dossier upload images (⚠ sur Render gratuit ça n'est pas persistant)
app.config["UPLOAD_FOLDER"] = "static/images"

db = SQLAlchemy(app)

# ---------- Modèles ----------
class Categorie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False, unique=True)
    articles = db.relationship("Article", backref="categorie", lazy=True)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prix = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(200), nullable=True)
    categorie_id = db.Column(db.Integer, db.ForeignKey("categorie.id"), nullable=True)

class Commande(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    total = db.Column(db.Float, nullable=False)

class Theme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    primary = db.Column(db.String(20), default="#ff003c")
    secondary = db.Column(db.String(20), default="#0a0a0a")

# ---------- Init DB au démarrage (crée les tables si absentes) ----------
with app.app_context():
    db.create_all()
    if not Theme.query.first():
        db.session.add(Theme(primary="#ff003c", secondary="#0a0a0a"))
        db.session.commit()

# ---------- Admin credentials ----------
ADMIN_USER = "getpost"
ADMIN_PASS = "tonght67"

# ---------- Utils ----------
def generer_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_theme():
    t = Theme.query.first()
    return {"primary": t.primary, "secondary": t.secondary} if t else {"primary": "#ff003c", "secondary": "#0a0a0a"}

# ---------- Routes ----------
@app.route("/")
def home():
    categories = Categorie.query.all()
    return render_template("categories.html", categories=categories, couleurs=get_theme())

@app.route("/categorie/<int:id>")
def categorie(id):
    cat = Categorie.query.get_or_404(id)
    return render_template("shop.html", categorie=cat, couleurs=get_theme())

@app.route("/produit/<int:id>")
def produit(id):
    article = Article.query.get_or_404(id)
    return render_template("produit.html", article=article, couleurs=get_theme())

@app.route("/ajouter_panier/<int:id>")
def ajouter_panier(id):
    panier = session.get("panier", [])
    panier.append(id)
    session["panier"] = panier
    return redirect(url_for("panier"))

@app.route("/panier", methods=["GET", "POST"])
def panier():
    panier = session.get("panier", [])
    items, total = [], 0
    for art_id in panier:
        a = Article.query.get(art_id)
        if a:
            items.append(a)
            total += a.prix

    if request.method == "POST" and items:
        code = generer_code()
        contenu = ", ".join([a.nom for a in items])
        db.session.add(Commande(code=code, contenu=contenu, total=total))
        db.session.commit()
        session.pop("panier", None)
        return render_template("confirmation.html", code=code, total=total, couleurs=get_theme())

    return render_template("panier.html", items=items, total=total, couleurs=get_theme())

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin"))
    return render_template("login.html", couleurs=get_theme())

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("home"))

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        return redirect(url_for("login"))

    if request.method == "POST":
        if "ajouter" in request.form:
            nom = request.form["nom"]
            prix = float(request.form["prix"])
            desc = request.form.get("description")
            categorie_id = request.form.get("categorie_id") or None

            image_file = request.files.get("image")
            image_filename = None
            if image_file and image_file.filename != "":
                try:
                    from pathlib import Path
                    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
                    filename = secure_filename(image_file.filename)
                    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    image_file.save(image_path)
                    image_filename = f"/static/images/{filename}"
                except Exception as e:
                    print(f"[ERREUR UPLOAD] {e}")

            article = Article(nom=nom, prix=prix, description=desc, image=image_filename, categorie_id=categorie_id)
            db.session.add(article)
            db.session.commit()

        elif "supprimer" in request.form:
            id_article = int(request.form["supprimer"])
            Article.query.filter_by(id=id_article).delete()
            db.session.commit()

        elif "ajouter_categorie" in request.form:
            nom_cat = request.form["categorie_nom"].strip()
            if nom_cat:
                db.session.add(Categorie(nom=nom_cat))
                db.session.commit()

        elif "supprimer_categorie" in request.form:
            id_cat = int(request.form["supprimer_categorie"])
            Categorie.query.filter_by(id=id_cat).delete()
            db.session.commit()

        elif "changer_couleurs" in request.form:
            t = Theme.query.first()
            t.primary = request.form["primary"]
            t.secondary = request.form["secondary"]
            db.session.commit()

    return render_template(
        "admin.html",
        articles=Article.query.all(),
        categories=Categorie.query.all(),
        commandes=Commande.query.all(),
        couleurs=get_theme()
    )

@app.route("/commande", methods=["POST"])
def commande():
    code = request.form["code"]
    commande = Commande.query.filter_by(code=code).first()
    return render_template("commande_resultat.html", commande=commande, couleurs=get_theme())

if __name__ == "__main__":
    # En local seulement (Render lancera gunicorn)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    app.run(debug=True)





