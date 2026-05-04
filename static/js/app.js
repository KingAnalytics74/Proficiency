function openModal(id) {
  document.getElementById(id).classList.remove('hidden');
}

function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
}

// Close modal on backdrop click
document.addEventListener('click', function (e) {
  if (e.target.classList.contains('modal')) {
    e.target.classList.add('hidden');
  }
});

// Edit menu item modal
function openEditModal(id, name, description, price, category, available) {
  document.getElementById('edit-name').value = name;
  document.getElementById('edit-description').value = description;
  document.getElementById('edit-price').value = price;
  document.getElementById('edit-category').value = category;
  document.getElementById('edit-available').checked = available;
  document.getElementById('edit-menu-form').action = '/menu/' + id + '/edit';
  openModal('edit-menu-modal');
}

// Dynamic order rows + live total
function addOrderRow() {
  const container = document.getElementById('order-items');
  if (!container) return;
  const first = container.querySelector('.order-item-row');
  const clone = first.cloneNode(true);
  clone.querySelector('select').value = '';
  clone.querySelector('input').value = 1;
  container.appendChild(clone);
  attachOrderListeners();
}

function attachOrderListeners() {
  document.querySelectorAll('#order-items select, #order-items input').forEach(function (el) {
    el.removeEventListener('change', updateTotal);
    el.removeEventListener('input', updateTotal);
    el.addEventListener('change', updateTotal);
    el.addEventListener('input', updateTotal);
  });
}

function updateTotal() {
  const rows = document.querySelectorAll('#order-items .order-item-row');
  let total = 0;
  rows.forEach(function (row) {
    const select = row.querySelector('select');
    const qty = parseInt(row.querySelector('input').value) || 0;
    const option = select.options[select.selectedIndex];
    const price = option ? parseFloat(option.dataset.price) || 0 : 0;
    total += price * qty;
  });
  const preview = document.getElementById('order-total');
  if (preview) {
    preview.textContent = total > 0 ? 'Estimated Total: $' + total.toFixed(2) : '';
  }
}

document.addEventListener('DOMContentLoaded', attachOrderListeners);
