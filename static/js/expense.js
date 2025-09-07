// Utility functions
function isNoneOrEmpty(value) {
    return !value || value.trim() === '';
}

function isSubset(subset, superset) {
    const supersetSet = new Set(superset.map(x => x.trim()));
    return subset.every(x => supersetSet.has(x.trim()));
}

function validateEqualSplit(groupMembers) {
    let paid_by = document.getElementById('paid_by').value;
    let splitBySelect = document.getElementById('split_by');
    let split_by = Array.from(splitBySelect.selectedOptions).map(opt => opt.value);
    let amount = document.getElementById('amount').value;
    let description = document.getElementById('description').value;

    if (isNoneOrEmpty(paid_by)) {
        return { valid: false, error: "Please select who paid" };
    }
    if (split_by.length < 2) {
        return { valid: false, error: "Please select at least 2 people to split between" };
    }
    if (isNoneOrEmpty(amount) || parseFloat(amount) <= 0) {
        return { valid: false, error: "Please enter a valid amount" };
    }
    if (isNoneOrEmpty(description)) {
        return { valid: false, error: "Please provide a description" };
    }

    let group_members_array = groupMembers.split(',').map(x => x.trim());
    if (!isSubset([paid_by], group_members_array) || !isSubset(split_by, group_members_array)) {
        return { valid: false, error: "The users involved do not belong to this group!" };
    }

    return { valid: true, error: "" };
}

function validateUnequalSplit(groupMembers) {
    try {
        let rows = document.querySelectorAll("#expensesTable tbody tr");
        if (rows.length === 0) {
            return { valid: false, error: "Add at least one split" };
        }

        let paid_by = [];
        let split_by = [];

        for (let row of rows) {
            let paid_by_row = row.querySelector('select[name="expense_by"]').value;
            let split_by_row = row.querySelector('select[name="expense_to"]').value;
            let amount = row.querySelector('input[name="expense_amount"]').value;
            let description = row.querySelector('input[name="expense_description"]').value;

            if (isNoneOrEmpty(paid_by_row)) {
                return { valid: false, error: "Blank item encountered: Paid By" };
            }
            if (isNoneOrEmpty(split_by_row)) {
                return { valid: false, error: "Blank item encountered: Split By" };
            }
            if (isNoneOrEmpty(amount)) {
                return { valid: false, error: "Blank item encountered: Amount" };
            }
            if (isNoneOrEmpty(description)) {
                return { valid: false, error: "Blank item encountered: Description" };
            }

            paid_by.push(paid_by_row);
            split_by.push(split_by_row);
        }

        let group_members_array = groupMembers.split(',').map(x => x.trim());
        let isValid = isSubset(paid_by, group_members_array) && isSubset(split_by, group_members_array);
        return {
            valid: isValid,
            error: isValid ? "" : "The users involved do not belong to this group!"
        };
    } catch (e) {
        console.error(e);
        return { valid: false, error: "An error occurred while validating the form" };
    }
}

// Initialize expense form functionality
function initializeExpenseForm() {
    const form = document.getElementById('transaction_form');
    const splitTypeRadios = document.getElementsByName('splitType');
    const equallyForm = document.getElementById('splitEquallyForm');
    const unequallyForm = document.getElementById('splitUnequallyForm');
    const isSplitEquallyInput = document.getElementById('is_split_equally');
    const modalElement = document.getElementById('createRecordModal');
    const addExpenseBtn = document.getElementById('addExpenseBtn');
    const expensesTable = document.getElementById('expensesTable').getElementsByTagName('tbody')[0];
    const groupMembers = document.getElementById('group_members').value;

    // Create template for new rows
    const rowTemplate = document.createElement('template');
    rowTemplate.innerHTML = `
        <tr>
            <td>
                <select class="form-select form-select-sm" name="expense_by" required>
                    <option value="">Select</option>
                    ${groupMembers.split(',').map(member =>
                        `<option value="${member.trim()}">${member.trim()}</option>`
                    ).join('')}
                </select>
            </td>
            <td>
                <select class="form-select form-select-sm" name="expense_to" required>
                    <option value="">Select</option>
                    ${groupMembers.split(',').map(member =>
                        `<option value="${member.trim()}">${member.trim()}</option>`
                    ).join('')}
                </select>
            </td>
            <td>
                <div class="input-group input-group-sm">
                    <span class="input-group-text">₹</span>
                    <input type="number" class="form-control" name="expense_amount" min="0" step="0.01" required placeholder="0.00">
                </div>
            </td>
            <td>
                <input type="text" class="form-control form-control-sm" name="expense_description" required placeholder="Description">
            </td>
            <td>
                <button type="button" class="btn btn-sm btn-outline-danger delete-row">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        </tr>
    `;

    // Handle split type toggle
    splitTypeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            const isEqual = e.target.value === 'equal';
            equallyForm.classList.toggle('d-none', !isEqual);
            unequallyForm.classList.toggle('d-none', isEqual);
            isSplitEquallyInput.value = isEqual;
        });
    });

    // Handle add row for unequal splits
    addExpenseBtn.addEventListener('click', () => {
        const newRow = rowTemplate.content.cloneNode(true);
        newRow.querySelector('.delete-row').addEventListener('click', function(e) {
            e.target.closest('tr').remove();
        });
        expensesTable.appendChild(newRow);
    });

    // Form validation
    form.addEventListener('submit', function(event) {
        event.preventDefault();

        const isEqual = document.getElementById('splitEquallyRadio').checked;
        let validation = isEqual ?
            validateEqualSplit(groupMembers) :
            validateUnequalSplit(groupMembers);

        if (!validation.valid) {
            alert(validation.error);
            return;
        }

        isSplitEquallyInput.value = isEqual;
        form.submit();
    });

    // Reset form when modal is shown (but preserve split method selection)
    modalElement.addEventListener('show.bs.modal', () => {
        // Reset form validation
        form.classList.remove('was-validated');
        form.reset();
        expensesTable.innerHTML = '';

        // Don't reset radio button selection - let it remember the previous choice
        // The form visibility will be set by the existing radio button change handler
    });

    // Reset form when modal is hidden (cleanup)
    modalElement.addEventListener('hidden.bs.modal', () => {
        form.classList.remove('was-validated');
        form.reset();
        expensesTable.innerHTML = '';
    });
}

// Initialize when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    // Wait for Bootstrap to be loaded
    if (typeof bootstrap !== 'undefined') {
        initializeExpenseForm();
    } else {
        // If Bootstrap isn't loaded yet, wait for it
        const checkBootstrap = setInterval(() => {
            if (typeof bootstrap !== 'undefined') {
                clearInterval(checkBootstrap);
                initializeExpenseForm();
            }
        }, 100);
    }
});
