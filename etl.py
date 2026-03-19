import sqlite3
import pandas as pd

OLTP_DB = "./Database/OLTP-Radio.db"
OLAP_DB = "./Database/OLAP-Radio.db"

def main():
    oltp = sqlite3.connect(OLTP_DB)
    olap = sqlite3.connect(OLAP_DB)

    # ---- Klant dimensie
    dim_klant = pd.read_sql("""
        SELECT 
            klant_id,
            voornaam,
            achternaam,
            stad,
            land,
            postcode,
            email
        FROM Klant
    """, oltp)

    dim_klant.insert(0, "klant_key", range(1, len(dim_klant) + 1))
    dim_klant.to_sql("Klant", olap, if_exists="replace", index=False)

    # ---- Product dimensie
    dim_product = pd.read_sql("""
        SELECT 
            p.product_id,
            p.naam AS product_naam,
            p.versie,
            p.verkoopprijs,
            p.inkoopprijs,
            p.introductiedatum,
            p.stopdatum,
            f.naam AS fabrikant_naam,
            f.land AS fabrikant_land,
            a.merk AS auto_merk,
            a.model AS auto_model,
            a.bouwjaar_van,
            a.bouwjaar_tot,
            a.generatie
        FROM Product p
        LEFT JOIN Fabrikant f ON p.fabrikant_id = f.fabrikant_id
        LEFT JOIN Auto_Product ap ON p.product_id = ap.product_id
        LEFT JOIN Auto a ON ap.auto_id = a.auto_id
    """, oltp)

    dim_product.insert(0, "product_key", range(1, len(dim_product) + 1))
    dim_product.to_sql("Product", olap, if_exists="replace", index=False)

    # ---- Datum dimensie
    verkoop_data = pd.read_sql("""
        SELECT verkoopdatum AS datum FROM Product_Verkoop
    """, oltp)

    review_data = pd.read_sql("""
        SELECT datum FROM Review
    """, oltp)

    inkoop_data = pd.read_sql("""
        SELECT inkoopdatum AS datum FROM Product_Inkoop
    """, oltp)

    alle_datums = pd.concat([verkoop_data, review_data, inkoop_data])
    alle_datums["datum"] = pd.to_datetime(alle_datums["datum"])
    alle_datums = alle_datums.drop_duplicates()

    dim_datum = pd.DataFrame()
    dim_datum["datum"] = alle_datums["datum"]
    dim_datum["dag"] = dim_datum["datum"].dt.day
    dim_datum["maand"] = dim_datum["datum"].dt.month
    dim_datum["maandnaam"] = dim_datum["datum"].dt.month_name()
    dim_datum["kwartaal"] = dim_datum["datum"].dt.quarter
    dim_datum["jaar"] = dim_datum["datum"].dt.year
    dim_datum["weeknummer"] = dim_datum["datum"].dt.isocalendar().week

    dim_datum.insert(0, "datum_key", range(1, len(dim_datum) + 1))
    dim_datum.to_sql("Datum", olap, if_exists="replace", index=False)

    #--- Verkoop fact
    fact_verkoop = pd.read_sql("""
        SELECT 
            vr.verkoop_id,
            vr.product_id,
            pv.klant_id,
            pv.verkoopdatum,
            vr.aantal,
            p.verkoopprijs,
            (vr.aantal * p.verkoopprijs) AS omzet,
            pv.status
        FROM Verkoop_regel vr
        JOIN Product_Verkoop pv ON vr.verkoop_id = pv.verkoop_id
        JOIN Product p ON vr.product_id = p.product_id
    """, oltp)

    fact_verkoop["verkoopdatum"] = pd.to_datetime(fact_verkoop["verkoopdatum"])

    # Koppel datum_key
    fact_verkoop = fact_verkoop.merge(
        dim_datum[["datum_key", "datum"]],
        left_on="verkoopdatum",
        right_on="datum",
        how="left"
    )

    # Koppel klant_key
    fact_verkoop = fact_verkoop.merge(
        dim_klant[["klant_key", "klant_id"]],
        on="klant_id",
        how="left"
    )

    # Koppel product_key
    fact_verkoop = fact_verkoop.merge(
        dim_product[["product_key", "product_id"]],
        on="product_id",
        how="left"
    )

    fact_verkoop = fact_verkoop[[
        "datum_key",
        "product_key",
        "klant_key",
        "aantal",
        "verkoopprijs",
        "omzet",
        "status"
    ]]

    fact_verkoop.insert(0, "verkoop_key", range(1, len(fact_verkoop) + 1))
    fact_verkoop.to_sql("Verkoop", olap, if_exists="replace", index=False)

    oltp.close()
    olap.close()

    print("ETL succesvol uitgevoerd.")


if __name__ == "__main__":
    main()