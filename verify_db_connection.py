
import psycopg


def test_auth(user, password, db):
    try:
        conn = psycopg.connect(
            user=user,
            password=password,
            dbname=db,
            host='127.0.0.1',
            port=5433
        )
        print(f"SUCCESS: {user}:{password}")
        conn.close()
        return True
    except Exception as e:
        print(f"FAIL: {user}:{password} -> {e}")
        return False

def main():
    creds = [
        ('foncier', 'foncier_2024', 'foncier_express'),
    ]

    for u, p, d in creds:
        if test_auth(u, p, d):
            break

if __name__ == "__main__":
    main()
