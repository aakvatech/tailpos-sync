import frappe
import uuid


# DEPRECATED
def generate_sales_invoice_daily():
    """Generate Sales Invoice from Receipts"""

    dates_query = """SELECT DATE(date) AS daily_date FROM `tabReceipts` GROUP BY DATE(date)"""

    dates = frappe.db.sql(dates_query, as_dict=1)

    for date in dates:
        generate_sales_invoice_by_date(date.daily_date)


# DEPRECATED
def receipts_by_date(date):
    """Retrieve Receipts by date"""

    receipts_query = """SELECT name FROM `tabReceipts` WHERE DATE(date)=%s"""

    receipts = frappe.db.sql(receipts_query, date, as_dict=1)

    return receipts


# DEPRECATED
def generate_sales_invoice_lines(name):
    """Create Sales Invoice from Receipts"""
    receipt = frappe.get_doc('Receipts', name)

    lines = []

    for line in receipt.receipt_lines:
        lines.append({
            'item_code': line.item_name,
            'item_name': line.item_name,
            'uom': 'Unit',
            'qty': line.qty,
            'rate': line.price
        })

    return lines


# DEPRECATED
def generate_sales_invoice_by_date(date):
    """Create Sales Invoice"""

    receipts = receipts_by_date(date)

    sales_invoice = frappe.get_doc({
        'doctype': 'Sales Invoice',
        'customer': 'Guest',
        'posting_date': date,
        'due_date': date,
        'title': date,
        'update_stock': 1,
    })

    for receipt in receipts:
        lines = generate_sales_invoice_lines(receipt.name)
        sales_invoice.db_set("total_taxes_and_charges", receipts.taxesvalue)
        sales_invoice.extend('items', lines)

    shifts = shifts_by_date(date)

    settings = frappe.get_doc('TailPOS Settings', 'TailPOS Settings')

    for shift in shifts:
        shift = frappe.get_doc('Shifts', shift.name)
        short_or_over = shift.actual_money - shift.ending_cash

        item_code = settings.shortages

        if short_or_over > 0:
            item_code = settings.overages

        sales_invoice.append('items', {
            'item_code': item_code,
            'rate': short_or_over,
            'qty': 1
        })

    try:
        sales_invoice.insert()
        sales_invoice.submit()
    except Exception as e:
        print(e)


# DEPRECATED
def sync_now():
    """Generates Sales Invoice Daily"""
    from frappe.utils.background_jobs import enqueue

    settings = frappe.get_doc('TailPOS Settings', 'TailPOS Settings')

    if settings.sales_invoice == 'By Daily Batch':
        enqueue('tailpos_sync.tailpos.generate_sales_invoice_today', timeout=2000, queue='long')


# DEPRECATED
def shifts_by_date(date):
    """Retrieve Shifts by date"""

    # Receipts query
    shifts_query = """SELECT name FROM `tabShifts` WHERE DATE(shift_beginning)=%s"""

    # Get all receipts
    shifts = frappe.db.sql(shifts_query, date, as_dict=1)

    return shifts


# DEPRECATED
def exists_sales_invoice_by_receipt(receipt):
    """Is there an existing Sales Invoice"""
    sales_invoices = frappe.get_all('Sales Invoice', filters={'remarks': receipt})
    if sales_invoices:
        return True
    return False


def get_receipt_items(receipt):
    fields = ['item', 'price', 'qty']
    return frappe.get_all('Receipts Item', filters={'parent': receipt}, fields=fields)

def get_items_with_price_list_query(device,columns=None, pos_profile=None,):

    if not pos_profile:
        pos_profile = frappe.db.get_single_value('Tail Settings', 'pos_profile')


    price_list = _get_price_list(pos_profile)
    item_group = get_device_item_group(device)
    categories = get_device_categories(device)
    condition = ""
    if len(item_group) > 0:
        condition += "AND ("
        for idx,i in enumerate(item_group):
            condition += "`tabItem`.item_group = '{0}' ".format(i)
            if int(idx) < int(len(item_group) - 1):
                condition += "OR"
        condition += ")"

    if len(categories) > 0:
        condition += "AND ("
        for idx, ii in enumerate(categories):
            condition += "`tabItem`.category = '{0}' ".format(ii)
            if int(idx) < int(len(categories) - 1):
                condition += "OR"
        condition += ")"

    columns_str = ', '.join(columns) if columns else '*'
    query = """
      SELECT %s FROM `tabItem` 
      INNER JOIN `tabItem Price` ON `tabItem`.name = `tabItem Price`.item_code
      LEFT JOIN `tabItem Tax` ON `tabItem`.name = `tabItem Tax`.parent
      
      WHERE `tabItem`.in_tailpos = 1 AND `tabItem Price`.price_list= '%s' {0}""".format(condition) % (columns_str, price_list)

    return query



def _get_price_list(pos_profile):
    price_list = frappe.db.get_value('POS Profile', pos_profile, 'selling_price_list')

    if not price_list:
        price_list = 'Standard Selling'

    return price_list

def get_device_item_group(device):
    device_item_group = []
    item_group = frappe.db.sql(""" SELECT item_group FROM `tabDevice Item Group` WHERE parent=%s """,(device))
    for i in item_group:
        device_item_group.append(i[0])
    return device_item_group

def get_device_categories(device):
    device_categories = []
    categories = frappe.db.sql(""" SELECT category FROM `tabDevice Category` WHERE parent=%s """,(device))
    for i in categories:
        device_categories.append(i[0])
    return device_categories
# Where is this called?
@frappe.whitelist()
def save_item(doc, method):
    # TODO: refactor(?)
    if doc.date_updated is None:
        doc.date_updated = doc.modified


def set_doc_id(doc):
    if not doc.id:
        doc.id = str(uuid.uuid4())


def set_date_updated(doc):
    if doc.date_updated is None:
        doc.date_updated = doc.modified
