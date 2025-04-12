// --- Existing Variables (Make sure they are declared) ---
const merchantInfoDiv = document.getElementById('merchant-info');
const getReportBtn = document.getElementById('get-report-btn');
const checkAnomaliesBtn = document.getElementById('check-anomalies-btn');
const updateStockBtn = document.getElementById('update-stock-btn');
const chatMessages = document.getElementById('chat-messages');
const reportDisplay = document.getElementById('report-display');
const paretoChartCanvas = document.getElementById('pareto-chart');
const stockDropdownContainer = document.getElementById('stock-dropdown-container');
const stockDropdownTrigger = document.getElementById('stock-dropdown-trigger');
const stockDropdownMenu = document.getElementById('stock-dropdown-menu');
const updateStockOption = document.getElementById('update-stock-option');
const notifyStockOption = document.getElementById('notify-stock-option');
let paretoChart = null; // To keep track of the chart instance
// Use relative URL if frontend and backend are served from the same origin,
// otherwise use the full URL like 'http://127.0.0.1:5000/chat'
const CHATBOT_URL = '/chat'; // Adjusted assuming served from same origin or proxied

// --- Chat Variables ---
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const closeReportBtn = document.getElementById('close-report-btn'); // Make sure this is defined

// --- Loading Animation Frames ---
const thinkingFrames = ['/', '-', '\\', '|']; // Frames for the animation



// --- Functions ---

function fetchMerchantInfo() {
    // Simulate fetching data
    setTimeout(() => {
        merchantInfoDiv.textContent = "Merchant: Kodang Koding Kiding | Location: Virtual | ID: 1d4f2";
        displayMessage("Welcome to the MEX Assistant demo! How can I help you today?", 'bot');
    }, 500);
}

function displayMessage(message, sender, elementId = null) { // Added optional elementId
    let messageElement;
    if (elementId && document.getElementById(elementId)) {
        // If elementId is provided and exists, update it
        messageElement = document.getElementById(elementId);
    } else {
        // Otherwise, create a new element
        messageElement = document.createElement('div');
        if (elementId) {
            messageElement.id = elementId; // Assign ID if provided for a new element
        }
        messageElement.classList.add('message');
        messageElement.classList.add(sender === 'user' ? 'user-message' : 'bot-message');
        chatMessages.appendChild(messageElement);
    }

        // --- MODIFICATION START ---
    // Check if marked and DOMPurify are available (basic check)
    if (typeof marked === 'object' && typeof DOMPurify === 'function') {
        try {
            // 1. Parse the Markdown string into raw HTML
            // You can configure Marked options here if needed: marked.parse(message, options)
            const rawHtml = marked.parse(message);

            // 2. Sanitize the generated HTML to prevent XSS attacks
            // Configure DOMPurify options if needed: DOMPurify.sanitize(rawHtml, config)
            const sanitizedHtml = DOMPurify.sanitize(rawHtml);

            // 3. Set the sanitized HTML as the element's content
            messageElement.innerHTML = sanitizedHtml;

        } catch (error) {
            // Log error and fallback to plain text if parsing/sanitizing fails
            console.error("Error processing Markdown:", error);
            messageElement.textContent = message; // Fallback
        }
    } else {
        // Fallback to textContent if libraries aren't loaded
        console.warn("Marked.js or DOMPurify not loaded. Displaying message as plain text.");
        messageElement.textContent = message;
    }
    // --- MODIFICATION END ---

    // Auto-scroll to the latest message
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return messageElement; // Return the element for potential further manipulation
}

// --- NEW: Reusable function to send message and display reply ---
async function fetchBotReply(messageToSend) {
    // 1. Setup for "thinking" animation
    let frameIndex = 0; // <--- ADDED BACK
    let thinkingIntervalId = null; // <--- ADDED BACK
    const thinkingElementId = `thinking-${Date.now()}`; // Unique ID for the thinking message

    // Display initial thinking message with first frame
    // UPDATED Text to include animation
    const thinkingMessageElement = displayMessage("Thinking " + thinkingFrames[frameIndex], 'bot', thinkingElementId);
    thinkingMessageElement.classList.add('thinking'); // Add class for potential styling

    // Start the animation interval // <--- ADDED BACK
    thinkingIntervalId = setInterval(() => {
        frameIndex = (frameIndex + 1) % thinkingFrames.length;
        // UPDATED Text to include animation
        thinkingMessageElement.textContent = "Thinking " + thinkingFrames[frameIndex];
    }, 200); // Update animation every 200ms


    // 2. Send message to Flask backend and get reply
    try {
        console.log("Sending to backend:", messageToSend);
        const response = await fetch(CHATBOT_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: messageToSend })
        });

        // Stop the animation FIRST // <--- ADDED BACK
        clearInterval(thinkingIntervalId);

        // 3. Handle response
        if (!response.ok) {
            console.error("Error from server:", response.status, response.statusText);
            const errorData = await response.json().catch(() => ({}));
            displayMessage(`Error: ${errorData.error || response.statusText || 'Failed to get reply'}`, 'bot', thinkingElementId);
            thinkingMessageElement.classList.remove('thinking');
            return;
        }

        const data = await response.json();

        if (data && data.reply) {
            displayMessage(data.reply, 'bot', thinkingElementId);
            thinkingMessageElement.classList.remove('thinking');
        } else {
            displayMessage("Received an empty or invalid reply from the server.", 'bot', thinkingElementId);
            thinkingMessageElement.classList.remove('thinking');
        }

    } catch (error) {
        // Stop the animation FIRST in case of network error // <--- ADDED BACK
        clearInterval(thinkingIntervalId);

        // 4. Handle network/fetch errors
        console.error("Network or fetch error:", error);
        const existingElement = document.getElementById(thinkingElementId);
         if (existingElement) {
             displayMessage("Sorry, I couldn't connect. Please check the backend server.", 'bot', thinkingElementId);
             existingElement.classList.remove('thinking');
        } else {
             displayMessage("Sorry, I couldn't connect. Please check the backend server.", 'bot');
        }
    }
}


// --- **MODIFIED** handleSendMessage (for user text input) ---
async function handleSendMessage() {
    const messageText = userInput.value.trim();
    if (messageText === '') {
        return;
    }

    // 1. Display the user's message immediately
    displayMessage(messageText, 'user');

    // 2. Clear the input field
    const currentMessage = userInput.value; // Store just before clearing
    userInput.value = '';
    userInput.focus(); // Keep focus on input

    // 3. Call the reusable function to get the bot reply
    await fetchBotReply(currentMessage); // Pass the user's typed message
}


// --- Event Listener for Closing the Report ---
if (closeReportBtn) { // Add a check in case the element isn't always present
    closeReportBtn.addEventListener('click', () => {
        if (reportDisplay) {
            reportDisplay.style.display = 'none'; // Hide the report area
        }
    });
}


// --- Existing Report/Anomaly/Chart/Update Functions (Keep them) ---
async function getReport() { 
    const messageForBackend = "get the latest report";
    displayMessage(`Okay, I will ${messageForBackend}.`, 'bot');
    await fetchBotReply(messageForBackend);
    merchantInfoDiv.style.border = "none";
}
function displayReport(reportData) { /* ... keep as is ... */ }

async function checkAnomalies() {
    // 1. Define the specific message to send for this action
    const messageForBackend = "check the system for anomalies";
    displayMessage(`Okay, I will ${messageForBackend}.`, 'bot');
    await fetchBotReply(messageForBackend);
    merchantInfoDiv.style.border = "none"; // Reset border, assuming reply explains status
}

function updateStock() {
    console.log("Update Stock button clicked - navigating to update_stock.html");
    window.location.href = 'update_stock.html'; // <--- THIS LINE
}


function createParetoChart(itemsData) { /* ... keep as is ... */ }

// --- Event Listeners ---
if (getReportBtn) getReportBtn.addEventListener('click', getReport);
if (checkAnomaliesBtn) checkAnomaliesBtn.addEventListener('click', checkAnomalies);
if (updateStockBtn) updateStockBtn.addEventListener('click', updateStock);

if (sendBtn) sendBtn.addEventListener('click', handleSendMessage);
if (userInput) {
    userInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.keyCode === 13) {
            event.preventDefault();
            handleSendMessage();
        }
    });
}



// --- Initial Load ---
document.addEventListener('DOMContentLoaded', () => {
    fetchMerchantInfo();
    if (reportDisplay) {
        reportDisplay.style.display = 'none';
    }
     // Add initial focus to the input field
     if (userInput) {
        userInput.focus();
    }
});

async function handleNotifyLowStocks() {
    console.log("Notify Low Stocks option clicked");
    stockDropdownMenu.classList.remove('show'); // Close dropdown immediately

    const messageForBackend = "notify me about low stock items";
    displayMessage(`Okay, I will ${messageForBackend}.`, 'bot'); // Inform user
    await fetchBotReply(messageForBackend); // Send request to backend
    // You might want to add specific UI feedback here if needed
}

if (stockDropdownTrigger && stockDropdownMenu) {
    stockDropdownTrigger.addEventListener('click', (event) => {
        event.stopPropagation(); // Prevent click from immediately closing menu via window listener
        stockDropdownMenu.classList.toggle('show');
    });

    // Close dropdown if clicked outside
    window.addEventListener('click', (event) => {
        if (!stockDropdownContainer.contains(event.target)) {
            stockDropdownMenu.classList.remove('show');
        }
    });
}

if (updateStockOption) {
    updateStockOption.addEventListener('click', handleUpdateStockList);
}

if (notifyStockOption) {
    notifyStockOption.addEventListener('click', handleNotifyLowStocks);
}

// --- Add these elements and functions to your stock update script ---

// Reference to the container where popups will appear
const stockAlertContainer = document.getElementById('stock-alert-container');

// Function to display a stock alert popup
function showStockAlertPopup(alertDetails) {
    if (!stockAlertContainer || !alertDetails) return;

    const popup = document.createElement('div');
    popup.className = 'stock-alert-popup';

    // Icon (you can use an actual icon library or emoji)
    const iconSpan = document.createElement('span');
    iconSpan.className = 'alert-icon';
    iconSpan.textContent = '⚠️'; // Warning emoji
    popup.appendChild(iconSpan);

    // Message
    const messageDiv = document.createElement('div');
    messageDiv.className = 'alert-message';
    messageDiv.innerHTML = `<strong>${alertDetails.productName} is low!</strong> Current: ${alertDetails.currentLevel} (Threshold: ${alertDetails.threshold})`;
    popup.appendChild(messageDiv);

    // Close Button
    const closeBtn = document.createElement('button');
    closeBtn.className = 'alert-close-btn';
    closeBtn.innerHTML = '×'; // 'x' symbol
    closeBtn.onclick = () => {
        popup.classList.remove('show');
        // Remove from DOM after animation
        setTimeout(() => popup.remove(), 450); // Match transition duration + buffer
    };
    popup.appendChild(closeBtn);

    // Add to container
    stockAlertContainer.appendChild(popup);

    // Trigger the show animation (needs slight delay after appending)
    setTimeout(() => popup.classList.add('show'), 50);

    // Auto-dismiss after some time (e.g., 7 seconds)
    setTimeout(() => {
        // Check if popup still exists before trying to remove
        if (popup && popup.classList.contains('show')) {
             closeBtn.onclick(); // Trigger the close logic
        }
    }, 7000); // 7 seconds
    function showStockAlertPopup(productName) {
        if (!stockAlertContainer || !productName) {
            console.warn("Missing alert container or product name for popup.");
            return;
        }
        console.log(`Showing alert popup for: ${productName}`); // Debug log
    
        const popup = document.createElement('div');
        popup.className = 'stock-alert-popup'; // Use the CSS class
    
        // Icon
        const iconSpan = document.createElement('span');
        iconSpan.className = 'alert-icon';
        iconSpan.textContent = '⚠️';
        popup.appendChild(iconSpan);
    
        // Simplified Message
        const messageDiv = document.createElement('div');
        messageDiv.className = 'alert-message';
        messageDiv.innerHTML = `<strong>${productName}</strong> stock is low!`;
        popup.appendChild(messageDiv);
    
        // Close Button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'alert-close-btn';
        closeBtn.innerHTML = '×';
        closeBtn.onclick = () => {
            popup.classList.remove('show');
            setTimeout(() => popup.remove(), 450); // Remove after fade out
        };
        popup.appendChild(closeBtn);
    
        // Add to container
        stockAlertContainer.appendChild(popup);
    
        // Trigger show animation
        setTimeout(() => popup.classList.add('show'), 50);
    
        // Auto-dismiss
        setTimeout(() => {
            if (popup && popup.classList.contains('show')) {
                 closeBtn.onclick();
            }
        }, 7000);
    }
}