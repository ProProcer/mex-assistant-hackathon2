document.addEventListener('DOMContentLoaded', () => {
    // Existing elements
    const inventoryTableBody = document.getElementById('inventory-table-body');
    const saveStockBtn = document.getElementById('save-stock-btn');
    const statusMessageDiv = document.getElementById('status-message');

    // --- NEW Elements for Adding Item ---
    const newItemNameInput = document.getElementById('new-stock-name-input');
    const newItemQuantityInput = document.getElementById('new-stock-quantity-input');
    const newItemUnitsInput = document.getElementById('new-stock-units-input');
    const addNewItemBtn = document.getElementById('add-new-item-btn');
    // Optional: Dedicated status message for adding
    const addItemStatusDiv = document.getElementById('add-item-status-message');


    let originalInventoryData = [];

    // Function to display status messages (can be reused or made specific)
    function showStatus(message, type = 'loading', targetDiv = statusMessageDiv) {
        if (!targetDiv) return;
        targetDiv.textContent = message;
        targetDiv.className = ''; // Clear previous classes
        // Add specific class if needed, e.g., for addItemStatusDiv styling
        if (targetDiv === addItemStatusDiv) {
             targetDiv.classList.add('add-item-status'); // Example class
        }
        targetDiv.classList.add(type); // Add type class (success, error, loading)
        targetDiv.style.display = 'block';
        if ((type === 'success' || type === 'error') && targetDiv !== addItemStatusDiv) {
            setTimeout(() => {
                targetDiv.style.display = 'none';
            }, 5000);
        }
        // Keep add item status visible until next action? Or timeout as well?
        if ((type === 'success' || type === 'error') && targetDiv === addItemStatusDiv) {
             setTimeout(() => {
                targetDiv.style.display = 'none';
            }, 5000); // Timeout for add item status too
        }
    }

    // Function to populate the table
     function populateTable(inventoryData) {
         if (!inventoryTableBody) return;
         inventoryTableBody.innerHTML = '';

         if (!inventoryData || inventoryData.length === 0) {
             // *** CHANGE: Update colspan to 3 since Actions column is removed ***
             inventoryTableBody.innerHTML = '<tr><td colspan="3" style="text-align: center;">No inventory items found for this merchant.</td></tr>';
             return;
         }
         originalInventoryData = JSON.parse(JSON.stringify(inventoryData));

         inventoryData.forEach(item => {
             const row = document.createElement('tr');
             row.setAttribute('data-stock-name', item.stock_name);

             // Stock Name Cell (No change)
             const nameCell = document.createElement('td');
             nameCell.textContent = item.stock_name || 'N/A';
             row.appendChild(nameCell);

             // Current Quantity Cell (No change)
             const currentQtyCell = document.createElement('td');
             currentQtyCell.textContent = item.current_stock;
             if (item.units) {
                 const unitsSpan = document.createElement('span');
                 unitsSpan.classList.add('units');
                 unitsSpan.textContent = item.units;
                 currentQtyCell.appendChild(document.createTextNode(' '));
                 currentQtyCell.appendChild(unitsSpan);
             }
             currentQtyCell.classList.add('current-quantity');
             row.appendChild(currentQtyCell);

             // *** START CHANGES for New Quantity Cell ***
             const newQtyCell = document.createElement('td');
             newQtyCell.classList.add('new-quantity-cell'); // Add a class for easier CSS targeting

             // Create Quantity Input (No change)
             const input = document.createElement('input');
             input.type = 'number';
             input.min = '0';
             input.value = item.current_stock;
             input.classList.add('new-quantity-input');
             input.setAttribute('aria-label', `New quantity for ${item.stock_name || 'item'}`);
             newQtyCell.appendChild(input); // Add input first

             // --- Create and Add Action Elements directly into this cell ---
             const actionContainer = document.createElement('div');
             actionContainer.classList.add('action-container');

             const dotsBtn = document.createElement('button');
             dotsBtn.classList.add('action-dots-btn');
             dotsBtn.innerHTML = '&#8942;'; // Vertical ellipsis
             dotsBtn.title = 'Actions';

             const dropdown = document.createElement('div');
             dropdown.classList.add('action-dropdown');

             const deleteBtn = document.createElement('button');
             deleteBtn.classList.add('delete-stock-btn');
             deleteBtn.textContent = 'Delete';

             // Event listener for dots button
             dotsBtn.addEventListener('click', (event) => {
                 event.stopPropagation();
                 document.querySelectorAll('.action-dropdown').forEach(d => {
                     if (d !== dropdown) d.style.display = 'none';
                 });
                 dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
             });

             // Event listener for delete button
             deleteBtn.addEventListener('click', () => {
                 const stockNameToDelete = item.stock_name;
                 deleteStockItem(stockNameToDelete);
                 dropdown.style.display = 'none';
             });

             // Assemble and append actions
             dropdown.appendChild(deleteBtn);
             actionContainer.appendChild(dotsBtn);
             actionContainer.appendChild(dropdown);
             newQtyCell.appendChild(actionContainer); // Append actions container *after* input

             row.appendChild(newQtyCell); // Add the combined cell to the row

             inventoryTableBody.appendChild(row); // Add the completed row
         });
     }


    // --- Add this new function outside populateTable ---
    async function deleteStockItem(stockName) {
        if (!stockName) {
            console.error("No stock name provided for deletion.");
            showStatus("Could not determine item to delete.", "error");
            return;
        }

        // Confirmation dialog (recommended)
        if (!confirm(`Are you sure you want to permanently delete all entries for "${stockName}"? This cannot be undone.`)) {
            return; // User cancelled
        }

        showStatus(`Deleting "${stockName}"...`, 'loading');

        try {
            const response = await fetch('/api/merchant/stock_delete', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ stock_name: stockName })
            });

            const result = await response.json().catch(() => ({})); // Attempt to parse JSON

            if (!response.ok) {
                throw new Error(result.error || `Server error deleting item: ${response.status}`);
            }

            console.log(`Deletion successful for ${stockName}:`, result);
            showStatus(result.message || `Successfully deleted "${stockName}".`, 'success');

            // Refresh the inventory table to reflect the deletion
            await fetchInventory();

        } catch (error) {
            console.error(`Error deleting stock item "${stockName}":`, error);
            showStatus(`Error deleting "${stockName}": ${error.message}`, 'error');
        } finally {
            // You might want to disable buttons during the process, re-enable here
        }
    }

    // --- Add a global click listener to close dropdowns ---
    document.addEventListener('click', () => {
        document.querySelectorAll('.action-dropdown').forEach(d => {
            d.style.display = 'none';
        });
    });

    // Function to fetch inventory data (No changes needed here)
    async function fetchInventory() {
        // ... (keep existing fetchInventory logic) ...
        showStatus('Loading inventory...', 'loading');
        try {
            const response = await fetch('/api/merchant/inventory');
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP error ${response.status}: ${response.statusText}`);
            }
            const data = await response.json();
            data.sort((a, b) => (a.stock_name || '').localeCompare(b.stock_name || ''));
            populateTable(data);
            statusMessageDiv.style.display = 'none'; // Hide main loading message
        } catch (error) {
            console.error('Error fetching inventory:', error);
            showStatus(`Error loading inventory: ${error.message}`, 'error');
            inventoryTableBody.innerHTML = `<tr><td colspan="3" style="text-align: center;">Error loading data.</td></tr>`;
        }
    }

    // Function to handle saving changes to existing items (No changes needed here)
    async function saveChanges() {
        // ... (keep existing saveChanges logic) ...
        if (!saveStockBtn || !inventoryTableBody) return;
        showStatus('Saving changes...', 'loading');
        saveStockBtn.disabled = true;
        const updates = [];
        const rows = inventoryTableBody.querySelectorAll('tr[data-stock-name]');
        let hasInvalidInput = false;
        rows.forEach(row => {
            const stockName = row.getAttribute('data-stock-name');
            if (!stockName) return;
            const newQtyInput = row.querySelector('.new-quantity-input');
            if (!newQtyInput) return;
            const originalItem = originalInventoryData.find(item => item.stock_name === stockName);
            if (!originalItem) {
                 console.warn(`Could not find original data for stock name: ${stockName}`);
                 return;
            }
            const originalStock = parseInt(originalItem.current_stock, 10);
            let newStock;
            try {
                const rawValue = newQtyInput.value.trim();
                if (rawValue === '') {
                     throw new Error("Input is empty");
                }
                 newStock = parseInt(rawValue, 10);
                 if (isNaN(newStock) || newStock < 0) {
                     throw new Error("Value is not a non-negative integer");
                 }
            } catch (e) {
                console.warn(`Invalid stock value for ${stockName}: "${newQtyInput.value}" (${e.message})`);
                newQtyInput.style.border = '2px solid red';
                hasInvalidInput = true;
                return;
            }
            newQtyInput.style.border = '';
            if (originalStock !== newStock) {
                updates.push({
                    stock_name: stockName,
                    new_stock: newStock
                });
            }
        });
        if (hasInvalidInput) {
            showStatus('Please fix invalid entries (marked in red) before saving.', 'error');
            saveStockBtn.disabled = false;
            return;
        }
        if (updates.length === 0) {
            showStatus('No changes detected in existing items.', 'success');
            saveStockBtn.disabled = false;
            return;
        }
        try {
            const response = await fetch('/api/merchant/stock_update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', },
                body: JSON.stringify({ updates: updates })
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) {
                 if (response.status === 207 && result.status === 'partial_success') {
                     console.warn('Partial success updating stock:', result.details);
                     const successCount = result.details?.success?.length || 0;
                     const failedCount = result.details?.failed?.length || 0;
                     showStatus(`Partial success. Updated: ${successCount}, Failed: ${failedCount}. Check logs.`, 'error');
                     await fetchInventory();
                 } else {
                     throw new Error(result.error || `Server responded with status ${response.status}`);
                 }
            } else {
                console.log('Stock updated successfully:', result);
                showStatus(`Successfully updated ${updates.length} existing item(s).`, 'success');
                await fetchInventory();
            }
        } catch (error) {
            console.error('Error saving stock updates:', error);
            showStatus(`Error saving changes: ${error.message}`, 'error');
        } finally {
            saveStockBtn.disabled = false;
        }
    }


    // --- NEW Function to handle adding a new stock item ---
    async function addNewStockItem() {
        if (!newItemNameInput || !newItemQuantityInput || !newItemUnitsInput || !addNewItemBtn) {
            console.error("Add item input elements not found");
            return;
        }

        const stockName = newItemNameInput.value.trim();
        const quantityStr = newItemQuantityInput.value.trim();
        const units = newItemUnitsInput.value.trim(); // Units are optional backend-wise, but good practice

        // --- Validation ---
        newItemNameInput.style.border = '';
        newItemQuantityInput.style.border = '';
        let isValid = true;
        let errorMsg = '';

        if (!stockName) {
            errorMsg = 'Stock name cannot be empty.';
            newItemNameInput.style.border = '2px solid red';
            isValid = false;
        }

        let quantityInt;
        if (!quantityStr) {
             errorMsg += (errorMsg ? ' ' : '') + 'Quantity cannot be empty.';
             newItemQuantityInput.style.border = '2px solid red';
             isValid = false;
        } else {
            quantityInt = parseInt(quantityStr, 10);
            if (isNaN(quantityInt) || quantityInt < 0) {
                errorMsg += (errorMsg ? ' ' : '') + 'Quantity must be a non-negative number.';
                newItemQuantityInput.style.border = '2px solid red';
                isValid = false;
            }
        }

         // Optional: Check for duplicates before sending to backend
         const existingItem = originalInventoryData.find(item => item.stock_name.toLowerCase() === stockName.toLowerCase());
         if (existingItem) {
             errorMsg += (errorMsg ? ' ' : '') + `Item "${stockName}" already exists. Please update it in the table above.`;
             newItemNameInput.style.border = '2px solid red';
             isValid = false;
         }


        if (!isValid) {
            showStatus(errorMsg, 'error', addItemStatusDiv); // Show error near the add form
            return;
        }

        // Disable button during API call
        addNewItemBtn.disabled = true;
        showStatus('Adding item...', 'loading', addItemStatusDiv);

        // --- Prepare Payload ---
        const newItemData = {
            stock_name: stockName,
            new_stock: quantityInt,
            // Include units in the payload for the backend to potentially use
            units: units
        };

        try {
            const response = await fetch('/api/merchant/stock_update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                // Send as an array with one item, matching the endpoint expectation
                body: JSON.stringify({ updates: [newItemData] })
            });

            const result = await response.json().catch(() => ({})); // Attempt to parse JSON

            if (!response.ok) {
                // Handle potential errors from the backend (e.g., if even the single item failed)
                 throw new Error(result.error || `Server error adding item: ${response.status}`);
            } else {
                 // Check if the backend reported partial success (which shouldn't happen for a single item unless there's an issue)
                 if (result.status === 'partial_success' && result.details?.failed?.length > 0) {
                     throw new Error(result.details.failed[0]?.reason || "Backend failed to add item.");
                 }
                 // Full success
                 console.log('New item added successfully:', result);
                 showStatus(`Successfully added item: ${stockName}.`, 'success', addItemStatusDiv);

                 // Clear the input fields
                 newItemNameInput.value = '';
                 newItemQuantityInput.value = '';
                 newItemUnitsInput.value = '';

                 // Refresh the main inventory table to show the new item
                 await fetchInventory();
            }
        } catch (error) {
            console.error('Error adding new stock item:', error);
            showStatus(`Error adding item: ${error.message}`, 'error', addItemStatusDiv);
        } finally {
            addNewItemBtn.disabled = false; // Re-enable button
        }
    }


    // --- Event Listeners ---
    if (saveStockBtn) {
        saveStockBtn.addEventListener('click', saveChanges);
    }
    // --- NEW Event Listener for Add Item Button ---
    if (addNewItemBtn) {
        addNewItemBtn.addEventListener('click', addNewStockItem);
    }

    // --- Initial Load ---
    fetchInventory();
});