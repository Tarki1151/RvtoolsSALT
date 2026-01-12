"""
Datastores API Routes
"""
from flask import Blueprint, jsonify, request
import pandas as pd

from utils.db import get_db_connection

datastores_bp = Blueprint('datastores', __name__, url_prefix='/api')


@datastores_bp.route('/datastores')
def api_datastores():
    """Get list of all datastores with physical storage info"""
    source = request.args.get('source', None)
    conn = get_db_connection()
    
    try:
        if source:
            df_ds = pd.read_sql_query(
                "SELECT * FROM vDatastore WHERE Source=?", conn, params=(source,)
            )
            df_mp = pd.read_sql_query(
                'SELECT Datastore, Vendor, Model, "Serial #" FROM vMultiPath WHERE Source=?',
                conn, params=(source,)
            )
        else:
            df_ds = pd.read_sql_query("SELECT * FROM vDatastore", conn)
            df_mp = pd.read_sql_query(
                'SELECT Datastore, Vendor, Model, "Serial #" FROM vMultiPath', conn
            )

        # Merge with multipath to get Vendor/Model
        df_mp_unique = df_mp.drop_duplicates(subset=['Datastore'])
        df_combined = df_ds.merge(df_mp_unique, left_on='Name', right_on='Datastore', how='left')
        
        # Clean numeric columns
        cols_to_fix = ['Capacity MiB', 'Free MiB', 'Provisioned MiB', 'In Use MiB', '# VMs', '# Hosts']
        for col in cols_to_fix:
            if col in df_combined.columns:
                df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce').fillna(0)

        return jsonify(df_combined.fillna('').to_dict('records'))
    except Exception as e:
        print(f"Error in api_datastores: {e}")
        return jsonify([])
    finally:
        conn.close()
