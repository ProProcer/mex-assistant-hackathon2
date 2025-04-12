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

function renderChart(chartPayload, containerElement) {
    // --- DEBUG LOGGING ---
    console.log("[renderChart] Received containerElement:", containerElement);
    console.log("[renderChart] Received chartPayload:", JSON.stringify(chartPayload, null, 2)); // Log full payload
    // --- END DEBUG LOGGING ---

    const { chart_type, chart_data, options } = chartPayload;

    if (!containerElement) {
        console.error("[renderChart] Error: containerElement is null or undefined.");
        // Optionally display an error message in the main chat
        displayMessage("[System Error: Chart container not found.]", 'bot');
        return;
    }

    if (chart_type !== 'bar') {
        console.error("[renderChart] Unsupported chart type received:", chart_type);
        containerElement.textContent = `[System: Received chart data but type '${chart_type}' is not supported yet.]`;
        containerElement.classList.remove('thinking');
        return;
    }

    // Validate chart_data structure minimally
    if (!chart_data || !chart_data.labels || (!chart_data.data && !chart_data.datasets)) {
         console.error("[renderChart] Invalid chart_data structure received:", chart_data);
         containerElement.textContent = `[System: Invalid chart data structure received.]`;
         containerElement.classList.remove('thinking');
         return;
    }


    // Clear the container
    containerElement.innerHTML = '';
    containerElement.classList.remove('thinking');

    // Create canvas
    const canvas = document.createElement('canvas');
    containerElement.appendChild(canvas);
    containerElement.classList.add('chart-container'); // Add specific class for styling
    // --- DEBUG LOGGING ---
    console.log("[renderChart] Created canvas element:", canvas);
    // --- END DEBUG LOGGING ---


    // **Modify Chart.js data structure slightly for bar charts if needed**
    let finalChartData;
    if (chart_data.labels && chart_data.data && !chart_data.datasets) {
         console.log("[renderChart] Wrapping simple labels/data into datasets structure for Chart.js");
         finalChartData = {
             labels: chart_data.labels,
             datasets: [{
                 label: options?.title || 'Sales Data', // Use chart title or default
                 data: chart_data.data,
                 backgroundColor: 'rgba(0, 177, 79, 0.6)', // Example: Grab green
                 borderColor: 'rgba(0, 177, 79, 1)',
                 borderWidth: 1
             }]
         };
    } else if (chart_data.datasets) {
         console.log("[renderChart] Using datasets structure provided by backend.");
         finalChartData = chart_data; // Use as is
    } else {
         // This case should be caught by the earlier validation, but good to have a fallback
         console.error("[renderChart] Final check failed: Invalid chart_data structure: Missing labels or data/datasets.");
         containerElement.textContent = "[System: Chart rendering failed - invalid data structure.]";
         containerElement.classList.remove('chart-container');
         return;
    }
    // --- DEBUG LOGGING ---
    console.log("[renderChart] Using finalChartData:", JSON.stringify(finalChartData, null, 2));
    // --- END DEBUG LOGGING ---


    // Configure Chart.js
    const ctx = canvas.getContext('2d');
    if (!ctx) {
        console.error("[renderChart] Failed to get canvas context.");
        containerElement.textContent = "[System: Failed to get canvas context.]";
        containerElement.classList.remove('chart-container');
        return;
    }
    // --- DEBUG LOGGING ---
    console.log("[renderChart] Canvas context obtained:", ctx);
    // --- END DEBUG LOGGING ---

    const chartConfig = {
        type: 'bar',
        data: finalChartData, // Use the potentially modified data structure
        options: {
            responsive: true,
            maintainAspectRatio: false, // Often better for chat containers
            plugins: {
                title: {
                    display: !!options?.title,
                    text: options?.title || '',
                    font: { size: 16 } // Example: make title larger
                },
                legend: {
                     // Display legend ONLY if there are multiple datasets
                    display: finalChartData.datasets && finalChartData.datasets.length > 1,
                    position: 'top',
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: !!options?.x_label,
                        text: options?.x_label || 'Date' // Default X label
                    },
                    // Reduce number of labels shown if there are too many
                    ticks: {
                         autoSkip: true,
                         maxTicksLimit: 15 // Adjust as needed
                    }
                },
                y: {
                    display: true,
                    beginAtZero: true,
                    title: {
                        display: !!options?.y_label,
                        text: options?.y_label || 'Sales (USD)' // Default Y label
                    }
                }
            }
        }
    };
    // --- DEBUG LOGGING ---
    console.log("[renderChart] Final chartConfig:", JSON.stringify(chartConfig, null, 2));
    // --- END DEBUG LOGGING ---


    // Create the chart instance
    try {
        console.log("[renderChart] Attempting to create new Chart instance...");
        new Chart(ctx, chartConfig);
        console.log("[renderChart] Chart instance created successfully.");
    } catch (error) {
        console.error("[renderChart] Chart.js error:", error); // Log the specific error
        containerElement.textContent = `[System: Failed to render chart. Error: ${error.message}]`;
        containerElement.classList.remove('chart-container');
    }
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
        const thinkingElement = document.getElementById(thinkingElementId);
        if (thinkingElement) {
            try {
                chatMessages.removeChild(thinkingElement);
            } catch (removeError) {
                // Ignore if element already removed somehow
                console.warn("Could not remove thinking element, maybe already gone?", removeError);
            }
        }

        const data = await response.json();

        if (data) {
            let textAnswer = null;
            let chartCommand = null;

            // Check if it's the structured response { "answer": "...", "chart_command": {...} }
            if (typeof data === 'object' && data !== null && (data.answer || data.chart_command)) {
                // --- DEBUG LOGGING ---
                console.log("[fetchBotReply] Processing structured response format.");
                // --- END DEBUG LOGGING ---
                textAnswer = data.answer; // Can be null if only chart is sent
                if (data.chart_command && data.chart_command.type === 'chart' && data.chart_command.payload) {
                    // --- DEBUG LOGGING ---
                    console.log("[fetchBotReply] Found valid chart command in structured response.");
                    // --- END DEBUG LOGGING ---
                     chartCommand = data.chart_command; // Store the whole chart command object
                } else if (data.chart_command) {
                    // --- DEBUG LOGGING ---
                    console.warn("[fetchBotReply] Found chart_command but it was invalid:", data.chart_command);
                    // --- END DEBUG LOGGING ---
                }
           }
           // Fallback: Check if it's just a plain text answer (e.g., old format, error string from backend)
           else if (typeof data.answer === 'string') {
                // --- DEBUG LOGGING ---
                console.log("[fetchBotReply] Processing simple string response in 'answer' field.");
                // --- END DEBUG LOGGING ---
                textAnswer = data.answer;
           }
           // Fallback: Check legacy 'reply' key
           else if (data.reply && typeof data.reply === 'string') {
               // --- DEBUG LOGGING ---
               console.log("[fetchBotReply] Processing legacy 'reply' field.");
               // --- END DEBUG LOGGING ---
               textAnswer = data.reply;
               // Attempt to parse if it *might* be a chart command string (old logic)
               try {
                    const parsedReply = JSON.parse(textAnswer);
                    if (parsedReply && parsedReply.type === 'chart' && parsedReply.payload) {
                         // --- DEBUG LOGGING ---
                         console.warn("[fetchBotReply] Parsed legacy chart command from 'reply' field.");
                         // --- END DEBUG LOGGING ---
                         chartCommand = parsedReply;
                         textAnswer = null; // Don't display the raw JSON string as text
                    }
               } catch(e) { /* Ignore parse error, it's just text */ }
           }

           // --- DEBUG LOGGING ---
           console.log("[fetchBotReply] Parsed textAnswer:", textAnswer);
           console.log("[fetchBotReply] Parsed chartCommand:", chartCommand ? JSON.stringify(chartCommand) : null);
           // --- END DEBUG LOGGING ---


           // --- Display content ---
           if (textAnswer) {
                // --- DEBUG LOGGING ---
                console.log("[fetchBotReply] Displaying text answer.");
                // --- END DEBUG LOGGING ---
                displayMessage(textAnswer, 'bot');
           }

           if (chartCommand && chartCommand.payload) {
                // --- DEBUG LOGGING ---
                console.log("[fetchBotReply] Preparing to render chart.");
                // --- END DEBUG LOGGING ---
                // Create a new message div specifically for the chart
                const chartMessageElement = displayMessage("", 'bot'); // Create empty bot message div
                // --- DEBUG LOGGING ---
                console.log("[fetchBotReply] Created chart message element:", chartMessageElement);
                // --- END DEBUG LOGGING ---
                renderChart(chartCommand.payload, chartMessageElement); // Render chart into it
           } else if (!textAnswer && !chartCommand) {
                // --- DEBUG LOGGING ---
                console.log("[fetchBotReply] Received empty or invalid reply content.");
                // --- END DEBUG LOGGING ---
                displayMessage("[Received empty or invalid reply]", 'bot');
           }

       } else {
           // --- DEBUG LOGGING ---
           console.log("[fetchBotReply] Received null or undefined data object from backend.");
           // --- END DEBUG LOGGING ---
           displayMessage("[Received empty or invalid data object]", 'bot');
       }
       // --- End Handling ---

    } catch (error) {
        clearInterval(thinkingIntervalId); // Stop animation on network error
        console.error("[fetchBotReply] Network or fetch error:", error); // Log the specific error
        // Attempt to remove thinking message even on error
        const thinkingElementOnError = document.getElementById(thinkingElementId);
        if (thinkingElementOnError) {
            try { chatMessages.removeChild(thinkingElementOnError); } catch (e) {}
        }
        displayMessage("Sorry, I couldn't connect or process the request. Please check the backend or try again.", 'bot');
    } finally {
        // Re-enable input/button if needed
        if (userInput) userInput.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
        if (userInput) userInput.focus();
        console.log("[fetchBotReply] Processing finished."); // Log end of function
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
    userInput.disabled = true; // Disable input during processing
    sendBtn.disabled = true;
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
            if (!userInput.disabled) {
                event.preventDefault(); // Prevent form submission/newline
                handleSendMessage();
            }
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
    if (!window.Chart) {
        console.error("Chart.js library not loaded!");
        displayMessage("[System Error: Chart library not found. Charts cannot be displayed.]", 'bot');
    } else {
        console.log("Chart.js library loaded successfully.");
    }
});