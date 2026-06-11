"""Patch Django's SQLite schema editor for Turso migrations."""
import re
import logging

logger = logging.getLogger("turso_backend.patch")

_REMAKE_PREFIX = "new__"


def _fix_migration_sql(sql):
    """Fix INSERT INTO ... SELECT SQL for column mismatches."""
    if "INSERT INTO" not in sql.upper() or "SELECT FROM" not in sql.upper():
        return sql
    
    if "new__" not in sql.lower():
        return sql
    
    # Parse the SQL more carefully
    # INSERT INTO "table" (col1, col2) SELECT ... FROM "table2"
    pattern = re.compile(
        r'INSERT\s+INTO\s+[`"\'\[]?(\w+)[`"\'\]]?\s*\(([^)]+)\)\s*SELECT\s+(.+?)\s+FROM\s+[`"\'\[]?(\w+)[`"\'\]]?',
        re.IGNORECASE | re.DOTALL
    )
    
    match = pattern.search(sql)
    if not match:
        return sql
    
    dest_table = match.group(1)
    dest_cols_raw = match.group(2)
    src_table = match.group(4)
    
    if not dest_table.startswith(_REMAKE_PREFIX):
        return sql
    
    # Parse destination columns
    dest_cols = [c.strip().strip('`"\'[] ') for c in dest_cols_raw.split(',') if c.strip()]
    
    logger.info("Processing %s: cols=%s", dest_table, dest_cols)
    
    # For contenttypes migration, remove 'name' column
    if dest_table == "new__django_content_type":
        fixed_cols = [c for c in dest_cols if c.lower() != "name"]
        if len(fixed_cols) < len(dest_cols):
            quoted = ", ".join('"' + c + '"' for c in fixed_cols)
            fixed_sql = 'INSERT INTO "' + dest_table + '" (' + quoted + ') SELECT ' + quoted + ' FROM "' + src_table + '"'
            logger.info("Fixed SQL: %s", fixed_sql)
            return fixed_sql
    
    return sql


def patch_django_schema_editor():
    """Patch Django's SQLite schema editor."""
    try:
        from django.db.backends.sqlite3.schema import DatabaseSchemaEditor
        
        _original_execute = DatabaseSchemaEditor.execute
        
        def patched_execute(self, sql, params=None):
            # Fix the SQL before executing
            if sql:
                fixed_sql = _fix_migration_sql(str(sql))
                if fixed_sql != str(sql):
                    logger.info("Patched SQL: %s", fixed_sql[:150])
                    sql = fixed_sql
            
            return _original_execute(self, sql, params)
        
        DatabaseSchemaEditor.execute = patched_execute
        logger.info("Patched Django SQLite schema editor")
        
    except Exception as e:
        logger.error("Failed to patch: %s", e)


# Apply patch immediately
patch_django_schema_editor()
