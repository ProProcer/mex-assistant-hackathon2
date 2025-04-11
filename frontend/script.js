// --- Existing Variables (Make sure they are declared) ---
const merchantInfoDiv = document.getElementById('merchant-info');
const getReportBtn = document.getElementById('get-report-btn');
const checkAnomaliesBtn = document.getElementById('check-anomalies-btn');
const updateStockBtn = document.getElementById('update-stock-btn');
const chatMessages = document.getElementById('chat-messages');
const reportDisplay = document.getElementById('report-display');
const paretoChartCanvas = document.getElementById('pareto-chart');
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
    window.location.href = 'update_stock.html'; // Navigate to the new page
}

// --- Make sure the event listener is still attached ---
if (updateStockBtn) updateStockBtn.addEventListener('click', updateStock);


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