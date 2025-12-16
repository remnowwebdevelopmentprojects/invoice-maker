from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import re
import traceback
from html import escape
from weasyprint import HTML, CSS
from io import BytesIO
import zipfile
import tempfile
import shutil
from dotenv import load_dotenv
import hashlib
import secrets
import base64

load_dotenv()

app = Flask(__name__, static_folder='assets', static_url_path='/assets')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'postgresql://postgres:12345@localhost:5432/remnow_invoice')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    quotation_prefix = db.Column(db.String(50), default='QUO/25-26/')
    invoice_prefix = db.Column(db.String(50), default='INV/25-26/')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    quotations = db.relationship('Quotation', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Quotation(db.Model):
    __tablename__ = 'quotations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quotation_no = db.Column(db.String(100), unique=True, nullable=False)
    date = db.Column(db.Date, nullable=False)
    to_address = db.Column(db.Text, nullable=False)
    client_phone = db.Column(db.String(50))
    currency = db.Column(db.String(10), nullable=False, default='INR')
    document_type = db.Column(db.String(20), nullable=False, default='invoice')
    payment_status = db.Column(db.String(20), nullable=False, default='unpaid')
    
    bank_name = db.Column(db.String(200))
    branch_name = db.Column(db.String(200))
    account_name = db.Column(db.String(200))
    account_number = db.Column(db.String(50))
    ifsc_code = db.Column(db.String(20))
    gpay_phonepe = db.Column(db.String(50))
    
    # GST fields
    gst_type = db.Column(db.String(20))  # 'interstate' or 'intrastate'
    cgst_rate = db.Column(db.Numeric(5, 2))  # CGST percentage
    sgst_rate = db.Column(db.Numeric(5, 2))  # SGST percentage
    igst_rate = db.Column(db.Numeric(5, 2))  # IGST percentage
    
    items = db.Column(db.JSON, nullable=False)
    
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    share_token = db.Column(db.String(100), unique=True, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def generate_share_token(self):
        """Generate a unique share token for secure URL access"""
        if not self.share_token:
            # Create a unique token using secrets and hash
            unique_string = f"{self.id}-{self.quotation_no}-{secrets.token_hex(16)}"
            self.share_token = hashlib.sha256(unique_string.encode()).hexdigest()[:32]
        return self.share_token
    
    def to_dict(self):
        return {
            'id': self.id,
            'quotation_no': self.quotation_no,
            'date': self.date.strftime('%Y-%m-%d'),
            'to_address': self.to_address,
            'currency': self.currency,
            'document_type': self.document_type,
            'payment_status': self.payment_status,
            'bank_name': self.bank_name,
            'branch_name': self.branch_name,
            'account_name': self.account_name,
            'account_number': self.account_number,
            'ifsc_code': self.ifsc_code,
            'gpay_phonepe': self.gpay_phonepe,
            'gst_type': self.gst_type,
            'cgst_rate': float(self.cgst_rate) if self.cgst_rate else None,
            'sgst_rate': float(self.sgst_rate) if self.sgst_rate else None,
            'igst_rate': float(self.igst_rate) if self.igst_rate else None,
            'items': self.items,
            'total_amount': str(self.total_amount)
        }

class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    hsn_code = db.Column(db.String(50))
    default_rate = db.Column(db.Numeric(10, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'hsn_code': self.hsn_code or '',
            'default_rate': str(self.default_rate) if self.default_rate else ''
        }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid email or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not name or not email or not password:
            return render_template('register.html', error='All fields are required')
        
        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')
        
        if len(password) < 6:
            return render_template('register.html', error='Password must be at least 6 characters')
        
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email already registered')
        
        user = User(name=name, email=email)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    all_records = Quotation.query.filter_by(user_id=current_user.id).order_by(Quotation.created_at.desc()).all()
    quotations = [q for q in all_records if q.document_type == 'quotation']
    invoices = [q for q in all_records if q.document_type == 'invoice']
    
    return render_template('dashboard.html', quotations=quotations, invoices=invoices)

@app.route('/create')
@login_required
def create():
    return render_template('create.html')

@app.route('/edit/<int:quotation_id>')
@login_required
def edit(quotation_id):
    quotation = Quotation.query.filter_by(id=quotation_id, user_id=current_user.id).first_or_404()
    return render_template('create.html', quotation=quotation, edit_mode=True)

@app.route('/settings')
@login_required
def settings():
    items = Item.query.filter_by(user_id=current_user.id).order_by(Item.created_at.desc()).all()
    return render_template('settings.html', items=items)

@app.route('/api/items', methods=['GET'])
@login_required
def get_items():
    """Get all items for the current user"""
    items = Item.query.filter_by(user_id=current_user.id).order_by(Item.description).all()
    return jsonify([item.to_dict() for item in items])

@app.route('/api/items', methods=['POST'])
@login_required
def create_item():
    """Create a new item"""
    try:
        data = request.json
        item = Item(
            user_id=current_user.id,
            description=data.get('description', ''),
            hsn_code=data.get('hsn_code', ''),
            default_rate=float(data.get('default_rate', 0)) if data.get('default_rate') else None
        )
        db.session.add(item)
        db.session.commit()
        return jsonify({'message': 'Item created successfully', 'item': item.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
@login_required
def delete_item(item_id):
    """Delete an item"""
    try:
        item = Item.query.filter_by(id=item_id, user_id=current_user.id).first()
        if not item:
            return jsonify({'error': 'Item not found'}), 404
        db.session.delete(item)
        db.session.commit()
        return jsonify({'message': 'Item deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/prefixes', methods=['POST'])
@login_required
def update_prefixes():
    """Update document number prefixes"""
    try:
        data = request.json
        current_user.quotation_prefix = data.get('quotation_prefix', 'QUO/25-26/')
        current_user.invoice_prefix = data.get('invoice_prefix', 'INV/25-26/')
        db.session.commit()
        return jsonify({'message': 'Prefixes updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotation', methods=['POST'])
@login_required
def create_quotation():
    try:
        data = request.json
        
        required_fields = ['quotation_no', 'date', 'to_address', 'items', 'currency']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        total = 0
        for item in data['items']:
            if 'amount' in item and item['amount']:
                try:
                    total += float(item['amount'])
                except (ValueError, TypeError):
                    pass
        
        quotation = Quotation(
            user_id=current_user.id,
            quotation_no=data['quotation_no'],
            date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
            to_address=data['to_address'],
            client_phone=data.get('client_phone', ''),
            currency=data['currency'],
            document_type=data.get('document_type', 'invoice'),
            payment_status=data.get('payment_status', 'unpaid'),
            bank_name=data.get('bank_name', ''),
            branch_name=data.get('branch_name', ''),
            account_name=data.get('account_name', ''),
            account_number=data.get('account_number', '').strip() if data.get('account_number') else '',
            ifsc_code=data.get('ifsc_code', ''),
            gpay_phonepe=data.get('gpay_phonepe', ''),
            gst_type=data.get('gst_type'),
            cgst_rate=float(data.get('cgst_rate', 0)) if data.get('cgst_rate') else None,
            sgst_rate=float(data.get('sgst_rate', 0)) if data.get('sgst_rate') else None,
            igst_rate=float(data.get('igst_rate', 0)) if data.get('igst_rate') else None,
            items=data['items'],
            total_amount=total
        )
        
        db.session.add(quotation)
        db.session.flush()  # Get the ID before commit
        quotation.generate_share_token()  # Generate secure token
        db.session.commit()
        
        return jsonify({'message': 'Quotation created successfully', 'id': quotation.id}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotation/<int:quotation_id>', methods=['PUT'])
@login_required
def update_quotation(quotation_id):
    try:
        quotation = Quotation.query.filter_by(id=quotation_id, user_id=current_user.id).first_or_404()
        data = request.json
        
        required_fields = ['quotation_no', 'date', 'to_address', 'items', 'currency']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        total = 0
        for item in data['items']:
            if 'amount' in item and item['amount']:
                try:
                    total += float(item['amount'])
                except (ValueError, TypeError):
                    pass
        
        # Update quotation fields
        quotation.quotation_no = data['quotation_no']
        quotation.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        quotation.to_address = data['to_address']
        quotation.client_phone = data.get('client_phone', '')
        quotation.currency = data['currency']
        quotation.document_type = data.get('document_type', 'invoice')
        quotation.payment_status = data.get('payment_status', 'unpaid')
        quotation.bank_name = data.get('bank_name', '')
        quotation.branch_name = data.get('branch_name', '')
        quotation.account_name = data.get('account_name', '')
        quotation.account_number = data.get('account_number', '').strip() if data.get('account_number') else ''
        quotation.ifsc_code = data.get('ifsc_code', '')
        quotation.gpay_phonepe = data.get('gpay_phonepe', '')
        quotation.gst_type = data.get('gst_type')
        quotation.cgst_rate = float(data.get('cgst_rate', 0)) if data.get('cgst_rate') else None
        quotation.sgst_rate = float(data.get('sgst_rate', 0)) if data.get('sgst_rate') else None
        quotation.igst_rate = float(data.get('igst_rate', 0)) if data.get('igst_rate') else None
        quotation.items = data['items']
        quotation.total_amount = total
        
        db.session.commit()
        
        return jsonify({'message': 'Quotation updated successfully', 'id': quotation.id}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotation/<int:quotation_id>/pdf', methods=['GET'])
@login_required
def generate_pdf(quotation_id):
    try:
        quotation = Quotation.query.filter_by(id=quotation_id, user_id=current_user.id).first_or_404()
        
        formatted_date = quotation.date.strftime('%d-%b-%Y')
        
        address_lines = [line.strip() for line in quotation.to_address.split('\n') if line.strip()]
        if len(address_lines) > 0:
            company_name = address_lines[0]
            address_rest = '<br>'.join(address_lines[1:]) if len(address_lines) > 1 else ''
        else:
            company_name = quotation.to_address
            address_rest = ''
        
        is_quotation = quotation.document_type == 'quotation'
        doc_title = 'QUOTATION' if is_quotation else 'INVOICE'
        doc_label = 'Quotation' if is_quotation else 'Invoice'
        
        items_html = ''
        for index, item in enumerate(quotation.items, start=1):
            description = escape(item.get('description', ''))
            hsn_code = escape(item.get('hsn_code', '')) or ''
            month = escape(item.get('month', '')) or ''
            rate = escape(item.get('rate', '')) or ''
            amount = item.get('amount', '')
            
            month_display = month.replace(' ', '<br>') if month else ''
            
            if quotation.currency == 'USD':
                amount_display = f'${amount}' if amount else '$0.00'
            elif quotation.currency == 'INR':
                amount_display = f'₹{amount}' if amount else '₹0.00'
            else:
                amount_display = f'{quotation.currency} {amount}' if amount else f'{quotation.currency} 0.00'
            
            items_html += f'''                        <tr>
                            <td>
                                <p class="item-description">{index}. {description}</p>
                            </td>
                            <td class="text-center">{hsn_code}</td>
                            <td class="text-center">{month_display}</td>
                            <td class="text-center">{rate}</td>
                            <td class="text-right">{amount_display}</td>
                        </tr>
'''
        
        total_amount = float(quotation.total_amount)
        if quotation.currency == 'USD':
            total_display = f'${total_amount:.2f}'
            currency_text = 'In Dollars'
        elif quotation.currency == 'INR':
            total_display = f'₹{total_amount:.2f}'
            currency_text = 'In Rupees'
        else:
            total_display = f'{quotation.currency} {total_amount:.2f}'
            currency_text = f'In {quotation.currency}'
        
        # Calculate GST if currency is INR
        final_total = total_amount
        if quotation.currency == 'INR' and quotation.gst_type:
            items_html += f'''                        <tr class="total-row-subtotal">
                            <td colspan="3"></td>
                            <td class="text-center" style="border-top: 2px solid #000; font-weight: 700;">Sub Total</td>
                            <td class="text-right" style="border-top: 2px solid #000; font-weight: 700;">{total_display}</td>
                        </tr>
'''
            
            if quotation.gst_type == 'intrastate' and quotation.cgst_rate and quotation.sgst_rate:
                cgst_amount = total_amount * float(quotation.cgst_rate) / 100
                sgst_amount = total_amount * float(quotation.sgst_rate) / 100
                final_total = total_amount + cgst_amount + sgst_amount
                
                cgst_display = f'₹{cgst_amount:.2f}'
                sgst_display = f'₹{sgst_amount:.2f}'
                final_display = f'₹{final_total:.2f}'
                
                items_html += f'''                        <tr>
                            <td colspan="3"></td>
                            <td class="text-center" style="font-weight: 600;">CGST ({quotation.cgst_rate}%)</td>
                            <td class="text-right" style="font-weight: 600;">{cgst_display}</td>
                        </tr>
                        <tr>
                            <td colspan="3"></td>
                            <td class="text-center" style="font-weight: 600;">SGST ({quotation.sgst_rate}%)</td>
                            <td class="text-right" style="font-weight: 600;">{sgst_display}</td>
                        </tr>
'''
            elif quotation.gst_type == 'interstate' and quotation.igst_rate:
                igst_amount = total_amount * float(quotation.igst_rate) / 100
                final_total = total_amount + igst_amount
                
                igst_display = f'₹{igst_amount:.2f}'
                final_display = f'₹{final_total:.2f}'
                
                items_html += f'''                        <tr>
                            <td colspan="3"></td>
                            <td class="text-center" style="font-weight: 600;">IGST ({quotation.igst_rate}%)</td>
                            <td class="text-right" style="font-weight: 600;">{igst_display}</td>
                        </tr>
'''
            
            items_html += f'''                        <tr>
                            <td colspan="5" style="padding: 0; border: none;"></td>
                        </tr>
                        <tr class="total-row-final">
                            <td style="font-weight: 700; font-size: 14px;">Total ({currency_text})</td>
                            <td class="text-center"></td>
                            <td class="text-center"></td>
                            <td class="text-center"></td>
                            <td class="text-right" style="font-weight: 700; font-size: 14px;">{final_display}</td>
                        </tr>
'''
        else:
            items_html += f'''                        <tr class="total-row-subtotal">
                            <td colspan="3"></td>
                            <td class="text-center" style="border-top: 2px solid #000; font-weight: 700;">Sub Total</td>
                            <td class="text-right" style="border-top: 2px solid #000; font-weight: 700;">{total_display}</td>
                        </tr>
                        <tr>
                            <td colspan="5" style="padding: 0; border: none;"></td>
                        </tr>
                        <tr class="total-row-final">
                            <td style="font-weight: 700; font-size: 14px;">Total ({currency_text})</td>
                            <td class="text-center"></td>
                            <td class="text-center"></td>
                            <td class="text-center"></td>
                            <td class="text-right" style="font-weight: 700; font-size: 14px;">{total_display}</td>
                        </tr>
'''
        
        template_file = 'templates/layout/quotation.html' if is_quotation else 'templates/layout/index.html'
        with open(template_file, 'r', encoding='utf-8') as f:
            html_template = f.read()
        
        if not is_quotation:
            html_content = re.sub(r'<h2 class="invoice-title">INVOICE</h2>',
                                 f'<h2 class="invoice-title">{doc_title}</h2>',
                                 html_template)
        else:
            html_content = html_template
        
        if not is_quotation:
            html_content = re.sub(r'<span class="invoice-label">Invoice No:</span>',
                                 f'<span class="invoice-label">{doc_label} No:</span>',
                                 html_content)
        
        html_content = re.sub(r'<h3 class="client-name"></h3>',
                             f'<h3 class="client-name">{escape(company_name)}</h3>',
                             html_content)
        html_content = html_content.replace('<p class="client-address"></p>',
                                          f'<p class="client-address">{address_rest}</p>')
        
        details_pattern = r'(<div class="invoice-details">.*?<span class="invoice-label">' + doc_label + r' No:</span>\s*<span class="invoice-value">)(</span>.*?<span class="invoice-label">Date:</span>\s*<span class="invoice-value">)(</span>)'
        html_content = re.sub(details_pattern,
                             f'\\g<1>{escape(quotation.quotation_no)}\\g<2>{formatted_date}\\g<3>',
                             html_content,
                             flags=re.DOTALL)
        
        # Update currency symbol in table header
        if quotation.currency == 'USD':
            currency_label = 'Amount ($)'
        elif quotation.currency == 'INR':
            currency_label = 'Amount (Rs)'
        elif quotation.currency == 'EUR':
            currency_label = 'Amount (€)'
        elif quotation.currency == 'GBP':
            currency_label = 'Amount (£)'
        else:
            currency_label = f'Amount ({quotation.currency})'
        
        html_content = re.sub(r'<th class="text-right"[^>]*>Amount \([^)]+\)</th>',
                             f'<th class="text-right" style="width: 15%;">{currency_label}</th>',
                             html_content)
        
        # Insert all items into the table - let CSS handle pagination naturally
        items_pattern = r'(<tbody>\s*)<!--.*?-->(\s*</tbody>)'
        html_content = re.sub(items_pattern,
                             f'\\1\n{items_html}                    \\2',
                             html_content,
                             flags=re.DOTALL)
        
        if not is_quotation:
            html_content = re.sub(r'(<div><span class="payment-label">Bank Name:</span> <span class="payment-value">)</span></div>',
                                 f'\\1{escape(quotation.bank_name or "")}</span></div>',
                                 html_content)
            html_content = re.sub(r'(<div><span class="payment-label">Branch:</span> <span class="payment-value">)</span></div>',
                                 f'\\1{escape(quotation.branch_name or "")}</span></div>',
                                 html_content)
            html_content = re.sub(r'(<div><span class="payment-label">Account Name:</span> <span class="payment-value">)</span></div>',
                                 f'\\1{escape(quotation.account_name or "")}</span></div>',
                                 html_content)
            account_no_value = ""
            if quotation.account_number:
                clean_account = str(quotation.account_number).strip()
                if clean_account.lower().startswith('w'):
                    clean_account = clean_account[1:]
                account_no_value = escape(clean_account.strip())
            html_content = html_content.replace(
                '<span class="payment-label">Account No:</span> <span class="payment-value mono"></span>',
                f'<span class="payment-label">Account No:</span> <span class="payment-value mono">{account_no_value}</span>'
            )
            
            html_content = re.sub(r'(<div><span class="payment-label">IFSC Code:</span> <span class="payment-value">)</span></div>',
                                 f'\\1{escape(quotation.ifsc_code or "")}</span></div>',
                                 html_content)
            
            gpay_value = ""
            if quotation.gpay_phonepe:
                gpay_value = escape(str(quotation.gpay_phonepe).strip())
            
            html_content = html_content.replace(
                '<span class="payment-label">Gpay / PhonePe:</span> <span class="payment-value" style="font-weight: 600;"></span>',
                f'<span class="payment-label">Gpay / PhonePe:</span> <span class="payment-value" style="font-weight: 600;">{gpay_value}</span>'
            )
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # WeasyPrint needs file:// URLs for local assets on Windows
        # Convert backslashes to forward slashes for proper URI format
        assets_path = os.path.join(base_dir, 'assets').replace('\\', '/')
        html_content = html_content.replace('src="assets/', f'src="file:///{assets_path}/')
        
        try:
            # Create WeasyPrint HTML object
            html_doc = HTML(string=html_content, base_url=base_dir)
            
            # Define page CSS for A4 with no margins
            page_css = CSS(string='''
                @page {
                    size: A4;
                    margin: 0;
                }
            ''')
            
            # Generate PDF
            pdf_bytes = html_doc.write_pdf(stylesheets=[page_css])
            pdf_file = BytesIO(pdf_bytes)
            pdf_file.seek(0)
        except Exception as e:
            error_msg = str(e)
            raise Exception(f"PDF generation failed: {error_msg}")
        
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'quotation_{quotation.quotation_no}.pdf'
        )
        
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/quotation/<int:quotation_id>/whatsapp', methods=['GET'])
@login_required
def share_whatsapp(quotation_id):
    """Generate WhatsApp share link for a quotation/invoice with encrypted URL"""
    try:
        quotation = Quotation.query.filter_by(id=quotation_id, user_id=current_user.id).first_or_404()
        
        # Ensure token exists
        if not quotation.share_token:
            quotation.generate_share_token()
            db.session.commit()
        
        # Generate encrypted PDF URL using token
        pdf_url = request.url_root.rstrip('/') + url_for('view_shared_pdf', token=quotation.share_token)
        
        # Create WhatsApp message
        doc_type = 'Quotation' if quotation.document_type == 'quotation' else 'Invoice'
        message = f"Hi! Please find your {doc_type} from the belowp;: {pdf_url}"
        
        # URL encode the message for WhatsApp
        import urllib.parse
        encoded_message = urllib.parse.quote(message)
        
        # Return the WhatsApp URL
        whatsapp_url = f"https://wa.me/?text={encoded_message}"
        
        return jsonify({
            'whatsapp_url': whatsapp_url,
            'message': message,
            'pdf_url': pdf_url,
            'token': quotation.share_token
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/d/<token>', methods=['GET'])
def view_shared_pdf(token):
    """Public route to view PDF using encrypted token - no login required"""
    try:
        quotation = Quotation.query.filter_by(share_token=token).first_or_404()
        
        # Generate PDF using the existing generate_pdf logic
        formatted_date = quotation.date.strftime('%d-%b-%Y')
        
        address_lines = [line.strip() for line in quotation.to_address.split('\n') if line.strip()]
        if len(address_lines) > 0:
            company_name = address_lines[0]
            address_rest = '<br>'.join(address_lines[1:]) if len(address_lines) > 1 else ''
        else:
            company_name = quotation.to_address
            address_rest = ''
        
        is_quotation = quotation.document_type == 'quotation'
        doc_title = 'QUOTATION' if is_quotation else 'INVOICE'
        doc_label = 'Quotation' if is_quotation else 'Invoice'
        
        items_html = ''
        for index, item in enumerate(quotation.items, start=1):
            description = escape(item.get('description', ''))
            hsn_code = escape(item.get('hsn_code', '')) or ''
            month = escape(item.get('month', '')) or ''
            rate = escape(item.get('rate', '')) or ''
            amount = item.get('amount', '')
            
            month_display = month.replace(' ', '<br>') if month else ''
            
            if quotation.currency == 'USD':
                amount_display = f'${amount}' if amount else '$0.00'
            elif quotation.currency == 'INR':
                amount_display = f'₹{amount}' if amount else '₹0.00'
            else:
                amount_display = f'{quotation.currency} {amount}' if amount else f'{quotation.currency} 0.00'
            
            items_html += f'''                        <tr>
                            <td>
                                <p class="item-description">{index}. {description}</p>
                            </td>
                            <td class="text-center">{hsn_code}</td>
                            <td class="text-center">{month_display}</td>
                            <td class="text-center">{rate}</td>
                            <td class="text-right">{amount_display}</td>
                        </tr>
'''
        
        total_amount = float(quotation.total_amount)
        if quotation.currency == 'USD':
            total_display = f'${total_amount:.2f}'
            currency_text = 'In Dollars'
        elif quotation.currency == 'INR':
            total_display = f'₹{total_amount:.2f}'
            currency_text = 'In Rupees'
        else:
            total_display = f'{quotation.currency} {total_amount:.2f}'
            currency_text = f'In {quotation.currency}'
        
        # Calculate GST if currency is INR
        final_total = total_amount
        if quotation.currency == 'INR' and quotation.gst_type:
            items_html += f'''                        <tr class="total-row-subtotal">
                            <td colspan="3"></td>
                            <td class="text-center" style="border-top: 2px solid #000; font-weight: 700;">Sub Total</td>
                            <td class="text-right" style="border-top: 2px solid #000; font-weight: 700;">{total_display}</td>
                        </tr>
'''
            
            if quotation.gst_type == 'intrastate' and quotation.cgst_rate and quotation.sgst_rate:
                cgst_amount = total_amount * float(quotation.cgst_rate) / 100
                sgst_amount = total_amount * float(quotation.sgst_rate) / 100
                final_total = total_amount + cgst_amount + sgst_amount
                
                cgst_display = f'₹{cgst_amount:.2f}'
                sgst_display = f'₹{sgst_amount:.2f}'
                final_display = f'₹{final_total:.2f}'
                
                items_html += f'''                        <tr>
                            <td colspan="3"></td>
                            <td class="text-center" style="font-weight: 600;">CGST ({quotation.cgst_rate}%)</td>
                            <td class="text-right" style="font-weight: 600;">{cgst_display}</td>
                        </tr>
                        <tr>
                            <td colspan="3"></td>
                            <td class="text-center" style="font-weight: 600;">SGST ({quotation.sgst_rate}%)</td>
                            <td class="text-right" style="font-weight: 600;">{sgst_display}</td>
                        </tr>
'''
            elif quotation.gst_type == 'interstate' and quotation.igst_rate:
                igst_amount = total_amount * float(quotation.igst_rate) / 100
                final_total = total_amount + igst_amount
                
                igst_display = f'₹{igst_amount:.2f}'
                final_display = f'₹{final_total:.2f}'
                
                items_html += f'''                        <tr>
                            <td colspan="3"></td>
                            <td class="text-center" style="font-weight: 600;">IGST ({quotation.igst_rate}%)</td>
                            <td class="text-right" style="font-weight: 600;">{igst_display}</td>
                        </tr>
'''
            
            items_html += f'''                        <tr>
                            <td colspan="5" style="padding: 0; border: none;"></td>
                        </tr>
                        <tr class="total-row-final">
                            <td style="font-weight: 700; font-size: 14px;">Total ({currency_text})</td>
                            <td class="text-center"></td>
                            <td class="text-center"></td>
                            <td class="text-center"></td>
                            <td class="text-right" style="font-weight: 700; font-size: 14px;">{final_display}</td>
                        </tr>
'''
        else:
            items_html += f'''                        <tr class="total-row-subtotal">
                            <td colspan="3"></td>
                            <td class="text-center" style="border-top: 2px solid #000; font-weight: 700;">Sub Total</td>
                            <td class="text-right" style="border-top: 2px solid #000; font-weight: 700;">{total_display}</td>
                        </tr>
                        <tr>
                            <td colspan="5" style="padding: 0; border: none;"></td>
                        </tr>
                        <tr class="total-row-final">
                            <td style="font-weight: 700; font-size: 14px;">Total ({currency_text})</td>
                            <td class="text-center"></td>
                            <td class="text-center"></td>
                            <td class="text-center"></td>
                            <td class="text-right" style="font-weight: 700; font-size: 14px;">{total_display}</td>
                        </tr>
'''
        
        template_file = 'templates/layout/quotation.html' if is_quotation else 'templates/layout/index.html'
        with open(template_file, 'r', encoding='utf-8') as f:
            html_template = f.read()
        
        if not is_quotation:
            html_content = re.sub(r'<h2 class="invoice-title">INVOICE</h2>',
                                 f'<h2 class="invoice-title">{doc_title}</h2>',
                                 html_template)
        else:
            html_content = html_template
        
        if not is_quotation:
            html_content = re.sub(r'<span class="invoice-label">Invoice No:</span>',
                                 f'<span class="invoice-label">{doc_label} No:</span>',
                                 html_content)
        
        html_content = re.sub(r'<h3 class="client-name"></h3>',
                             f'<h3 class="client-name">{escape(company_name)}</h3>',
                             html_content)
        html_content = html_content.replace('<p class="client-address"></p>',
                                          f'<p class="client-address">{address_rest}</p>')
        
        details_pattern = r'(<div class="invoice-details">.*?<span class="invoice-label">' + doc_label + r' No:</span>\s*<span class="invoice-value">)(</span>.*?<span class="invoice-label">Date:</span>\s*<span class="invoice-value">)(</span>)'
        html_content = re.sub(details_pattern,
                             f'\\g<1>{escape(quotation.quotation_no)}\\g<2>{formatted_date}\\g<3>',
                             html_content,
                             flags=re.DOTALL)
        
        # Smart table splitting
        num_items = len(quotation.items)
        first_table_html, second_table_html = split_table_html(items_html, num_items)
        
        items_pattern = r'(<tbody>\s*)<!--.*?-->(\s*</tbody>)'
        html_content = re.sub(items_pattern,
                             f'\\1\n{first_table_html}                    \\2',
                             html_content,
                             flags=re.DOTALL)
        
        # Insert second table if needed (after first table container)
        if second_table_html:
            # Find the closing tag of the first table container
            # Look for: </table>\n    </div> followed by optional whitespace and comments
            # This ensures we insert right after the first table, before any other content
            table_close_patterns = [
                r'(</table>\s*</div>\s*\n\s*\n\s*<!-- Totals)',
                r'(</table>\s*</div>\s*\n\s*\n\s*<!-- Spacer)',
                r'(</table>\s*</div>\s*\n\s*\n\s*<!--)',
                r'(</table>\s*</div>\s*\n\s*</div>)',  # Before closing content-wrapper
                r'(</table>\s*</div>)',  # Fallback: any table close
            ]
            
            inserted = False
            for pattern in table_close_patterns:
                match = re.search(pattern, html_content, re.MULTILINE | re.DOTALL)
                if match:
                    # Insert second table before the matched content
                    insert_pos = match.start(1)
                    html_content = html_content[:insert_pos] + second_table_html + html_content[insert_pos:]
                    inserted = True
                    break
            
            # Final fallback: use regex substitution
            if not inserted:
                html_content = re.sub(
                    r'(</table>\s*</div>)',
                    r'\1' + second_table_html,
                    html_content,
                    count=1,
                    flags=re.MULTILINE | re.DOTALL
                )
        
        if not is_quotation:
            html_content = re.sub(r'(<div><span class="payment-label">Bank Name:</span> <span class="payment-value">)</span></div>',
                                 f'\\1{escape(quotation.bank_name or "")}</span></div>',
                                 html_content)
            html_content = re.sub(r'(<div><span class="payment-label">Branch:</span> <span class="payment-value">)</span></div>',
                                 f'\\1{escape(quotation.branch_name or "")}</span></div>',
                                 html_content)
            html_content = re.sub(r'(<div><span class="payment-label">Account Name:</span> <span class="payment-value">)</span></div>',
                                 f'\\1{escape(quotation.account_name or "")}</span></div>',
                                 html_content)
            account_no_value = ""
            if quotation.account_number:
                clean_account = str(quotation.account_number).strip()
                if clean_account.lower().startswith('w'):
                    clean_account = clean_account[1:]
                account_no_value = escape(clean_account.strip())
            html_content = html_content.replace(
                '<span class="payment-label">Account No:</span> <span class="payment-value mono"></span>',
                f'<span class="payment-label">Account No:</span> <span class="payment-value mono">{account_no_value}</span>'
            )
            
            html_content = re.sub(r'(<div><span class="payment-label">IFSC Code:</span> <span class="payment-value">)</span></div>',
                                 f'\\1{escape(quotation.ifsc_code or "")}</span></div>',
                                 html_content)
            
            gpay_value = ""
            if quotation.gpay_phonepe:
                gpay_value = escape(str(quotation.gpay_phonepe).strip())
            
            html_content = html_content.replace(
                '<span class="payment-label">Gpay / PhonePe:</span> <span class="payment-value" style="font-weight: 600;"></span>',
                f'<span class="payment-label">Gpay / PhonePe:</span> <span class="payment-value" style="font-weight: 600;">{gpay_value}</span>'
            )
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # WeasyPrint handles file paths differently - use absolute paths
        html_content = html_content.replace('src="assets/', f'src="{base_dir}/assets/')
        
        try:
            # Create WeasyPrint HTML object
            html_doc = HTML(string=html_content, base_url=base_dir)
            
            # Define page CSS for A4 with no margins
            page_css = CSS(string='''
                @page {
                    size: A4;
                    margin: 0;
                }
            ''')
            
            # Generate PDF
            pdf_bytes = html_doc.write_pdf(stylesheets=[page_css])
            pdf_file = BytesIO(pdf_bytes)
            pdf_file.seek(0)
            
            return send_file(
                pdf_file,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'{quotation.quotation_no}.pdf'
            )
        except Exception as e:
            error_msg = str(e)
            raise Exception(f"PDF generation failed: {error_msg}")
        
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/quotation/<int:quotation_id>', methods=['GET'])
@login_required
def get_quotation(quotation_id):
    quotation = Quotation.query.filter_by(id=quotation_id, user_id=current_user.id).first_or_404()
    return jsonify(quotation.to_dict())

@app.route('/api/quotations', methods=['GET'])
@login_required
def list_quotations():
    quotations = Quotation.query.filter_by(user_id=current_user.id).order_by(Quotation.created_at.desc()).all()
    return jsonify([q.to_dict() for q in quotations])

@app.route('/bulk_export_count', methods=['POST'])
@login_required
def bulk_export_count():
    """Get the count of documents in the specified date range"""
    try:
        data = request.get_json()
        from_date = datetime.strptime(data['from_date'], '%Y-%m-%d').date()
        to_date = datetime.strptime(data['to_date'], '%Y-%m-%d').date()
        include_quotations = data.get('include_quotations', True)
        include_invoices = data.get('include_invoices', True)
        
        query_filter = (
            (Quotation.user_id == current_user.id) &
            (Quotation.created_at >= from_date) &
            (Quotation.created_at <= datetime.combine(to_date, datetime.max.time()))
        )
        
        documents = Quotation.query.filter(query_filter).all()
        
        total_count = 0
        for doc in documents:
            doc_type = doc.document_type.lower()
            if doc_type == 'quotation' and include_quotations:
                total_count += 1
            elif doc_type == 'invoice' and include_invoices:
                total_count += 1
        
        return jsonify({
            'total_documents': total_count,
            'quotations': sum(1 for doc in documents if doc.document_type.lower() == 'quotation' and include_quotations),
            'invoices': sum(1 for doc in documents if doc.document_type.lower() == 'invoice' and include_invoices)
        })
        
    except Exception as e:
        print(f"Bulk export count error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/bulk_export', methods=['POST'])
@login_required
def bulk_export():
    try:
        data = request.get_json()
        from_date = datetime.strptime(data['from_date'], '%Y-%m-%d').date()
        to_date = datetime.strptime(data['to_date'], '%Y-%m-%d').date()
        include_quotations = data.get('include_quotations', True)
        include_invoices = data.get('include_invoices', True)
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            quotations_dir = os.path.join(temp_dir, 'quotations')
            invoices_dir = os.path.join(temp_dir, 'invoices')
            
            if include_quotations:
                os.makedirs(quotations_dir, exist_ok=True)
            if include_invoices:
                os.makedirs(invoices_dir, exist_ok=True)
            
            query_filter = (
                (Quotation.user_id == current_user.id) &
                (Quotation.created_at >= from_date) &
                (Quotation.created_at <= datetime.combine(to_date, datetime.max.time()))
            )
            
            documents = Quotation.query.filter(query_filter).order_by(Quotation.created_at.desc()).all()
            
            if not documents:
                return jsonify({'error': 'No documents found in the specified date range'}), 404
            
            for doc in documents:
                doc_type = doc.document_type.lower()
                
                if doc_type == 'quotation' and not include_quotations:
                    continue
                if doc_type == 'invoice' and not include_invoices:
                    continue
                
                pdf_content = generate_pdf_content(doc)
                
                date_str = doc.created_at.strftime('%Y-%m-%d')
                doc_number = doc.quotation_no or f"DOC-{doc.id}"
                filename = f"{date_str}_{doc_number}_{doc_type}.pdf"
                
                filename = re.sub(r'[^\w\-_\.]', '_', filename)
                
                target_dir = quotations_dir if doc_type == 'quotation' else invoices_dir
                pdf_path = os.path.join(target_dir, filename)
                
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_content)
            
            zip_filename = f"bulk_export_{from_date}_{to_date}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if include_quotations and os.path.exists(quotations_dir):
                    for root, dirs, files in os.walk(quotations_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, temp_dir)
                            zipf.write(file_path, arcname)
                
                if include_invoices and os.path.exists(invoices_dir):
                    for root, dirs, files in os.walk(invoices_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, temp_dir)
                            zipf.write(file_path, arcname)
            
            return send_file(
                zip_path,
                as_attachment=True,
                download_name=zip_filename,
                mimetype='application/zip'
            )
            
        finally:
            def cleanup():
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            
            import atexit
            atexit.register(cleanup)
            
    except Exception as e:
        print(f"Bulk export error: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def split_table_html(items_html, num_items):
    """
    Intelligently split table HTML into multiple tables for proper pagination.
    Returns: (first_table_html, second_table_html_or_none)
    """
    # Conservative estimate: ~8-10 items fit on page 1 after header and client info
    # Adjust this based on your actual page layout
    ITEMS_PER_PAGE = 8
    
    if num_items <= ITEMS_PER_PAGE:
        return items_html, None
    
    # Find where totals start - look for the actual <tr> tag with the class
    totals_pattern = r'(<tr\s+class="total-row-subtotal">)'
    totals_match = re.search(totals_pattern, items_html)
    
    if not totals_match:
        # Try alternate pattern for final totals
        totals_pattern = r'(<tr\s+class="total-row-final">)'
        totals_match = re.search(totals_pattern, items_html)
    
    if not totals_match:
        # No totals found, return as-is
        return items_html, None
    
    totals_pos = totals_match.start()
    items_only = items_html[:totals_pos].strip()
    totals_html = items_html[totals_pos:]
    
    # Extract individual table rows using regex
    # This pattern matches complete <tr>...</tr> blocks including nested content
    # Using non-greedy match to get individual rows
    row_pattern = r'<tr[^>]*>.*?</tr>'
    rows = re.findall(row_pattern, items_only, re.DOTALL | re.MULTILINE)
    
    # Clean and validate rows - ensure they're actual data rows (have <td> tags)
    # Filter out empty rows or rows that don't contain table data
    cleaned_rows = []
    for row in rows:
        row = row.strip()
        if row and '<td' in row and 'item-description' in row:
            cleaned_rows.append(row)
    
    rows = cleaned_rows
    
    # Safety check: if we don't have enough rows, return original
    if len(rows) <= ITEMS_PER_PAGE:
        return items_html, None
    
    if len(rows) <= ITEMS_PER_PAGE:
        return items_html, None
    
    # Split rows: first page gets first ITEMS_PER_PAGE rows
    first_table_rows = rows[:ITEMS_PER_PAGE]
    remaining_rows = rows[ITEMS_PER_PAGE:]
    
    # Build first table HTML (with header - will be inserted into template)
    first_table_html = '\n'.join(first_table_rows)
    
    # Build second table HTML (no header, but with colgroup for perfect alignment)
    remaining_html = '\n'.join(remaining_rows)
    
    # Column widths matching the template exactly
    COLUMN_WIDTHS = [
        '35%',  # Description of Service
        '15%',  # HSN Code
        '15%',  # MONTH
        '20%',  # Rate
        '15%'   # Amount (Rs)
    ]
    
    colgroup_html = '\n'.join([f'                <col style="width: {width};">' for width in COLUMN_WIDTHS])
    
    # Ensure rows maintain proper indentation (24 spaces to match template)
    # The rows already have correct indentation from the regex match
    # Note: Don't include closing tags - insertion happens AFTER first table closes
    # Use minimal margins to avoid extra space
    second_table_html = f'''
    <div class="table-container" style="page-break-before: always; margin-top: 0; margin-bottom: 0;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; border: 1px solid #000; table-layout: fixed;">
            <colgroup>
{colgroup_html}
            </colgroup>
            <tbody>
{remaining_html}{totals_html}                    </tbody>
        </table>
    </div>
'''
    
    return first_table_html, second_table_html

def generate_pdf_content(quotation):
    """Generate PDF content for a quotation/invoice document"""
    try:
        is_quotation = quotation.document_type.lower() == 'quotation'
        
        if is_quotation:
            doc_title = 'QUOTATION'
            doc_label = 'Quotation'
        else:
            doc_title = 'INVOICE'
            doc_label = 'Invoice'
        
        items_html = ''
        for index, item in enumerate(quotation.items, start=1):
            description = escape(item.get('description', ''))
            hsn_code = escape(item.get('hsn_code', '')) or ''
            month = escape(item.get('month', '')) or ''
            rate = escape(item.get('rate', '')) or ''
            amount = item.get('amount', '')
            
            month_display = month.replace(' ', '<br>') if month else ''
            
            if quotation.currency == 'USD':
                amount_display = f'${amount}' if amount else '$0.00'
            elif quotation.currency == 'INR':
                amount_display = f'₹{amount}' if amount else '₹0.00'
            else:
                amount_display = f'{quotation.currency} {amount}' if amount else f'{quotation.currency} 0.00'
            
            items_html += f'''                        <tr>
                            <td>
                                <p class="item-description">{index}. {description}</p>
                            </td>
                            <td class="text-center">{hsn_code}</td>
                            <td class="text-center">{month_display}</td>
                            <td class="text-center">{rate}</td>
                            <td class="text-right">{amount_display}</td>
                        </tr>
'''
        
        total_amount = float(quotation.total_amount)
        if quotation.currency == 'USD':
            total_display = f'${total_amount:.2f}'
            currency_text = 'In Dollars'
        elif quotation.currency == 'INR':
            total_display = f'₹{total_amount:.2f}'
            currency_text = 'In Rupees'
        else:
            total_display = f'{quotation.currency} {total_amount:.2f}'
            currency_text = f'In {quotation.currency}'
        
        # Calculate GST if currency is INR
        final_total = total_amount
        if quotation.currency == 'INR' and quotation.gst_type:
            items_html += f'''                        <tr class="total-row-subtotal">
                            <td colspan="3"></td>
                            <td class="text-center" style="border-top: 2px solid #000; font-weight: 700;">Sub Total</td>
                            <td class="text-right" style="border-top: 2px solid #000; font-weight: 700;">{total_display}</td>
                        </tr>
'''
            
            if quotation.gst_type == 'intrastate' and quotation.cgst_rate and quotation.sgst_rate:
                cgst_amount = total_amount * float(quotation.cgst_rate) / 100
                sgst_amount = total_amount * float(quotation.sgst_rate) / 100
                final_total = total_amount + cgst_amount + sgst_amount
                
                cgst_display = f'₹{cgst_amount:.2f}'
                sgst_display = f'₹{sgst_amount:.2f}'
                final_display = f'₹{final_total:.2f}'
                
                items_html += f'''                        <tr>
                            <td colspan="3"></td>
                            <td class="text-center" style="font-weight: 600;">CGST ({quotation.cgst_rate}%)</td>
                            <td class="text-right" style="font-weight: 600;">{cgst_display}</td>
                        </tr>
                        <tr>
                            <td colspan="3"></td>
                            <td class="text-center" style="font-weight: 600;">SGST ({quotation.sgst_rate}%)</td>
                            <td class="text-right" style="font-weight: 600;">{sgst_display}</td>
                        </tr>
'''
            elif quotation.gst_type == 'interstate' and quotation.igst_rate:
                igst_amount = total_amount * float(quotation.igst_rate) / 100
                final_total = total_amount + igst_amount
                
                igst_display = f'₹{igst_amount:.2f}'
                final_display = f'₹{final_total:.2f}'
                
                items_html += f'''                        <tr>
                            <td colspan="3"></td>
                            <td class="text-center" style="font-weight: 600;">IGST ({quotation.igst_rate}%)</td>
                            <td class="text-right" style="font-weight: 600;">{igst_display}</td>
                        </tr>
'''
            
            items_html += f'''                        <tr>
                            <td colspan="5" style="padding: 0; border: none;"></td>
                        </tr>
                        <tr class="total-row-final">
                            <td style="font-weight: 700; font-size: 14px;">Total ({currency_text})</td>
                            <td class="text-center"></td>
                            <td class="text-center"></td>
                            <td class="text-center"></td>
                            <td class="text-right" style="font-weight: 700; font-size: 14px;">{final_display}</td>
                        </tr>
'''
        else:
            items_html += f'''                        <tr class="total-row-subtotal">
                            <td colspan="3"></td>
                            <td class="text-center" style="border-top: 2px solid #000; font-weight: 700;">Sub Total</td>
                            <td class="text-right" style="border-top: 2px solid #000; font-weight: 700;">{total_display}</td>
                        </tr>
                        <tr>
                            <td colspan="5" style="padding: 0; border: none;"></td>
                        </tr>
                        <tr class="total-row-final">
                            <td style="font-weight: 700; font-size: 14px;">Total ({currency_text})</td>
                            <td class="text-center"></td>
                            <td class="text-center"></td>
                            <td class="text-center"></td>
                            <td class="text-right" style="font-weight: 700; font-size: 14px;">{total_display}</td>
                        </tr>
'''
        
        template_file = 'templates/layout/quotation.html' if is_quotation else 'templates/layout/index.html'
        with open(template_file, 'r', encoding='utf-8') as f:
            html_template = f.read()
        
        if not is_quotation:
            html_content = re.sub(r'<h2 class="invoice-title">INVOICE</h2>',
                                 f'<h2 class="invoice-title">{doc_title}</h2>',
                                 html_template)
            html_content = re.sub(r'<span class="invoice-label">Invoice No:</span>',
                                 f'<span class="invoice-label">{doc_label} No:</span>',
                                 html_content)
        else:
            html_content = html_template
        
        address_lines = [line.strip() for line in quotation.to_address.split('\n') if line.strip()]
        if len(address_lines) > 0:
            company_name = address_lines[0]
            address_rest = '<br>'.join(address_lines[1:]) if len(address_lines) > 1 else ''
        else:
            company_name = quotation.to_address
            address_rest = ''
        
        html_content = re.sub(r'<h3 class="client-name"></h3>',
                             f'<h3 class="client-name">{escape(company_name)}</h3>',
                             html_content)
        html_content = html_content.replace('<p class="client-address"></p>',
                                          f'<p class="client-address">{address_rest}</p>')
        
        formatted_date = quotation.date.strftime('%d/%m/%Y')
        details_pattern = r'(<div class="invoice-details">.*?<span class="invoice-label">' + doc_label + r' No:</span>\s*<span class="invoice-value">)(</span>.*?<span class="invoice-label">Date:</span>\s*<span class="invoice-value">)(</span>)'
        html_content = re.sub(details_pattern,
                             f'\\g<1>{escape(quotation.quotation_no)}\\g<2>{formatted_date}\\g<3>',
                             html_content,
                             flags=re.DOTALL)
        
        # Update currency symbol in table header
        if quotation.currency == 'USD':
            currency_label = 'Amount ($)'
        elif quotation.currency == 'INR':
            currency_label = 'Amount (Rs)'
        elif quotation.currency == 'EUR':
            currency_label = 'Amount (€)'
        elif quotation.currency == 'GBP':
            currency_label = 'Amount (£)'
        else:
            currency_label = f'Amount ({quotation.currency})'
        
        html_content = re.sub(r'<th class="text-right"[^>]*>Amount \([^)]+\)</th>',
                             f'<th class="text-right" style="width: 15%;">{currency_label}</th>',
                             html_content)
        
        # Insert all items into the table - let CSS handle pagination naturally
        items_pattern = r'(<tbody>\s*)<!--.*?-->(\s*</tbody>)'
        html_content = re.sub(items_pattern,
                             f'\\1\n{items_html}                    \\2',
                             html_content,
                             flags=re.DOTALL)
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # WeasyPrint needs file:// URLs for local assets on Windows
        # Convert backslashes to forward slashes for proper URI format
        assets_path = os.path.join(base_dir, 'assets').replace('\\', '/')
        html_content = html_content.replace('src="assets/', f'src="file:///{assets_path}/')
        
        if not is_quotation:
            html_content = re.sub(r'(<div><span class="payment-label">Bank Name:</span> <span class="payment-value">)</span></div>',
                                 f'\\1{escape(quotation.bank_name or "")}</span></div>',
                                 html_content)
            html_content = re.sub(r'(<div><span class="payment-label">Branch:</span> <span class="payment-value">)</span></div>',
                                 f'\\1{escape(quotation.branch_name or "")}</span></div>',
                                 html_content)
            html_content = re.sub(r'(<div><span class="payment-label">Account Name:</span> <span class="payment-value">)</span></div>',
                                 f'\\1{escape(quotation.account_name or "")}</span></div>',
                                 html_content)
            
            account_no_value = ""
            if quotation.account_number:
                clean_account = str(quotation.account_number).strip()
                if clean_account.lower().startswith('w'):
                    clean_account = clean_account[1:]
                account_no_value = escape(clean_account.strip())
            html_content = html_content.replace(
                '<span class="payment-label">Account No:</span> <span class="payment-value mono"></span>',
                f'<span class="payment-label">Account No:</span> <span class="payment-value mono">{account_no_value}</span>'
            )
            
            html_content = re.sub(r'(<div><span class="payment-label">IFSC Code:</span> <span class="payment-value">)</span></div>',
                                 f'\\1{escape(quotation.ifsc_code or "")}</span></div>',
                                 html_content)
            
            gpay_value = ""
            if quotation.gpay_phonepe:
                gpay_value = escape(str(quotation.gpay_phonepe).strip())
            html_content = html_content.replace(
                '<span class="payment-label">Gpay / PhonePe:</span> <span class="payment-value" style="font-weight: 600;"></span>',
                f'<span class="payment-label">Gpay / PhonePe:</span> <span class="payment-value" style="font-weight: 600;">{gpay_value}</span>'
            )
        
        # Create WeasyPrint HTML object
        html_doc = HTML(string=html_content, base_url=base_dir)
        
        # Define page CSS for A4 with no margins
        page_css = CSS(string='''
            @page {
                size: A4;
                margin: 0;
            }
        ''')
        
        # Generate PDF
        pdf_content = html_doc.write_pdf(stylesheets=[page_css])
        return pdf_content
        
    except Exception as e:
        print(f"PDF generation error for document {quotation.id}: {str(e)}")
        traceback.print_exc()
        raise

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)

