"""Step 7: Optimize (VACUUM + CHECKPOINT)."""

from .utils import step_banner


def step_optimize(conn, dept):
    step_banner(7, "Optimize (VACUUM + CHECKPOINT)")
    conn.execute("VACUUM")
    conn.execute("CHECKPOINT")

    tables = conn.execute("SHOW TABLES").fetchall()
    print(f"  Tables: {', '.join(t[0] for t in tables)}")

    for t in tables:
        cnt = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
        print(f"    {t[0]:30s} {cnt:>12,}")
