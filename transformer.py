from sqlalchemy import Connection, text
from datasurface.platforms.yellow.transformerjob import DataTransformerContext


def executeTransformer(conn: Connection, context: DataTransformerContext) -> None:
    print(f"Executing transformer with {context}")
    sourceCustomerTableName = context.getInputTableNameForDataset("Original", "Store1", "customers")
    outputCustomerTableName = context.getOutputTableNameForDataset("customers")

    # Insert masked records using a single SQL statement
    insert_query = f"""
    INSERT INTO {outputCustomerTableName}
    (id, firstname, lastname, dob, email, phone, primaryaddressid, billingaddressid)
    SELECT
        id,
        CASE
            WHEN firstname IS NOT NULL THEN '***' || RIGHT(firstname, 2)
            ELSE NULL
        END as firstname,
        CASE
            WHEN lastname IS NOT NULL THEN '***' || RIGHT(lastname, 2)
            ELSE NULL
        END as lastname,
        dob,
        CASE
            WHEN email IS NOT NULL AND email LIKE '%@%'
            THEN LEFT(email, 3) || '***@' || SPLIT_PART(email, '@', 2)
            ELSE NULL
        END as email,
        CASE
            WHEN phone IS NOT NULL THEN '***-***-' || RIGHT(phone, 4)
            ELSE NULL
        END as phone,
        CASE
            WHEN primaryaddressid IS NOT NULL THEN '***' || RIGHT(primaryaddressid, 3)
            ELSE NULL
        END as primaryaddressid,
        CASE
            WHEN billingaddressid IS NOT NULL THEN '***' || RIGHT(billingaddressid, 3)
            ELSE NULL
        END as billingaddressid
    FROM {sourceCustomerTableName}
    """

    result = conn.execute(text(insert_query))
    print(f"Successfully processed and masked {result.rowcount} customer records")
