from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.secret_key = "supersecret"

# --- Config BDD ---
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///shop.db"
db = SQLAlchemy(app)

# --- Modèles ---
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prix = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(200), nullable=True)

class Commande(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    utilisateur = db.Column(db.String(100), nullable=False)
    article = db.Column(db.String(100), nullable=False)
    quantite = db.Column(db.Integer, default=1)

# --- Config admin ---
ADMIN_USER = "getpost"
ADMIN_PASS = "tonght67"

# --- Routes ---
@app.route("/")
def index():
    articles = Article.query.all()
    return render_template("index.html", articles=articles)

@app.route("/produit/<int:id>")
def produit(id):
    article = Article.query.get_or_404(id)
    return render_template("produit.html", article=article)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

@app.route("/admin", methods=["GET"])
def admin():
    if not session.get("admin"):
        return redirect(url_for("login"))

    articles = Article.query.all()
    commandes = Commande.query.all()

    # Couleurs par défaut
    couleurs = {"primary": "#e0112b", "secondary": "#111"}

    return render_template(
        "admin.html",
        articles=articles,
        commandes=commandes,
        couleurs=couleurs
    )

@app.route("/admin/add", methods=["POST"])
def add_article():
    if not session.get("admin"):
        return redirect(url_for("login"))

    nom = request.form["nom"]
    prix = request.form["prix"]
    desc = request.form["description"]
    image = None

    if "image" in request.files:
        img = request.files["image"]
        if img.filename:
            path = os.path.join("static/uploads", img.filename)
            img.save(path)
            image = path

    article = Article(nom=nom, prix=prix, description=desc, image=image)
    db.session.add(article)
    db.session.commit()
    return redirect(url_for("admin"))

@app.route("/admin/delete/<int:id>")
def delete_article(id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    article = Article.query.get_or_404(id)
    db.session.delete(article)
    db.session.commit()
    return redirect(url_for("admin"))

@app.route("/admin/theme", methods=["POST"])
def admin_theme():
    if not session.get("admin"):
        return redirect(url_for("login"))
    primary = request.form.get("primary")
    secondary = request.form.get("secondary")
    # ⚠️ Ici tu pourrais sauvegarder en BDD si tu veux persister les couleurs
    return redirect(url_for("admin"))

if __name__ == "__main__":
    if not os.path.exists("shop.db"):
        with app.app_context():
            db.create_all()
    app.run(debug=True)
