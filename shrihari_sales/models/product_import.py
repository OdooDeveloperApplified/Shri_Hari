import xmlrpc.client
import pandas as pd

url = "http://192.168.1.59:8095/"
db = "shri_hari"
username = "shri_hari"
password = "shri_hari"

file_path = "/home/applifiedtwo/Downloads/shree hari marketing ProductLedger.xlsx"

# Connect to Odoo
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
uid = common.authenticate(db, username, password, {})
print("UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)

# Read Excel
df = pd.read_excel(file_path)
df.columns = df.columns.str.strip()

# ✅ ONLY CHANGE → process 1 row for testing
# df = df.head(1)

success_count = 0
failed_count = 0

for index, row in df.iterrows():

    try:
        print(f"\n🔹 Processing Row {index + 1}")

        # -----------------------------
        # Product Values
        # -----------------------------
        product_vals = {
            'name': row['Product'],
            'is_storable': True,
        }

        print(f"product_vals : {product_vals}")

        # -----------------------------
        # Create Product
        # -----------------------------
        product_id = models.execute_kw(
            db, uid, password,
            'product.template',
            'create',
            [product_vals]
        )

        # -----------------------------
        # Get Product Variant
        # -----------------------------
        product_variant_id = models.execute_kw(
            db, uid, password,
            'product.product', 'search',
            [[['product_tmpl_id', '=', product_id]]],
            {'limit': 1}
        )[0]

        # -----------------------------
        # Quantity
        # -----------------------------
        qty = float(row['Closing Qty2']) if pd.notna(row['Closing Qty2']) else 0.0

        if qty > 0:
            # Get internal location
            location_id = models.execute_kw(
                db, uid, password,
                'stock.location', 'search',
                [[['usage', '=', 'internal']]],
                {'limit': 1}
            )[0]

            # Create quant
            quant_id = models.execute_kw(
                db, uid, password,
                'stock.quant', 'create',
                [{
                    'product_id': product_variant_id, 
                    'location_id': location_id,
                    'inventory_quantity': qty
                }]
            )

            # Apply inventory
            models.execute_kw(
                db, uid, password,
                'stock.quant', 'action_apply_inventory',
                [[quant_id]]
            )

        print(f"✅ Product created: {row['Product']} (ID: {product_id})")
        success_count += 1

    except Exception as e:
        print(f"❌ Error in row {index + 1}: {str(e)}")
        failed_count += 1

print("\n==============================")
print(f"✅ Success Count : {success_count}")
print(f"❌ Failed Count  : {failed_count}")
print("==============================")