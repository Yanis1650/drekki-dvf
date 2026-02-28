"""ETL build utilities."""


def step_banner(step_num, title):
    print(f"\n{'='*60}")
    print(f"  Etape {step_num}/7 : {title}")
    print(f"{'='*60}")


def print_distribution(conn, label):
    rows = conn.execute("""
        SELECT categorie, COUNT(*) as n,
               ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 1) as pct
        FROM densification_scores
        GROUP BY categorie
        ORDER BY CASE categorie
            WHEN 'FORT' THEN 1 WHEN 'MOYEN' THEN 2
            WHEN 'FAIBLE' THEN 3 WHEN 'SATURE' THEN 4
            WHEN 'NON_MUTABLE' THEN 5 WHEN 'INCONNU' THEN 6
        END
    """).fetchall()
    print(f"\n  {label}:")
    for cat, n, pct in rows:
        bar = "#" * int(pct / 2)
        print(f"    {cat:15s} {n:>10,} ({pct:5.1f}%) {bar}")
    return rows
