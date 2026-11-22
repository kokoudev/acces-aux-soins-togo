"""Projet 2 — Exécute toute l'analyse dans l'ordre (environ 2 minutes).

Usage : python analyse/pipeline.py
"""
from __future__ import annotations

import distances
import indicateurs
import indice_typologie
import rapport
import solutions
import statistiques

if __name__ == "__main__":
    for module in [distances, indicateurs, statistiques, indice_typologie, solutions, rapport]:
        print(f"--- {module.__name__}")
        module.main()
