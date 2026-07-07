"""Create an admin user out-of-band.

Usage:
    python -m app.seed <email> <password> [name]
    # or from the app/ directory:  python seed.py <email> <password> [name]

Safe to run against an existing DB — it refuses to duplicate an email and will
promote an existing user to admin instead.
"""
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

from models import db, User  # noqa: E402


def main(argv):
    if len(argv) < 2:
        print("Usage: python -m app.seed <email> <password> [name]")
        return 1

    email = User.normalize_email(argv[0])
    password = argv[1]
    name = argv[2] if len(argv) > 2 else ""

    import server  # noqa: E402  (configures app + db)
    with server.app.app_context():
        existing = User.query.filter_by(email=email).first()
        if existing:
            existing.role = "admin"
            db.session.commit()
            print(f"User {email} already existed — promoted to admin.")
            return 0
        user = User(email=email, name=name, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Created admin {email}.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
