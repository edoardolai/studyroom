const form = document.getElementById("chat-form");
const input = document.getElementById("chat-body");
const sendButton = document.getElementById("chat-send");
const reconnectButton = document.getElementById("chat-reconnect");
const status = document.getElementById("chat-status");
const messages = document.getElementById("chat-messages");
const scheme = window.location.protocol === "https:" ? "wss" : "ws";
const socket = new WebSocket(`${scheme}://${window.location.host}/ws/courses/${form.dataset.course}/chat/`);
const shown = new Set();

function addMessage(message) {
    // History and a live broadcast can contain the same saved message.
    if (shown.has(message.id)) return;
    shown.add(message.id);
    const item = document.createElement("li");
    item.dataset.id = message.id;
    const heading = document.createElement("strong");
    heading.textContent = message.author;
    const time = document.createElement("time");
    time.dateTime = message.created_at;
    time.textContent = ` · ${new Date(message.created_at).toLocaleString()}`;
    const body = document.createElement("p");
    body.textContent = message.body;
    item.append(heading, time, body);
    const later = Array.from(messages.children).find(row => Number(row.dataset.id) > message.id);
    messages.insertBefore(item, later || null);
    messages.scrollTop = messages.scrollHeight;
}

socket.onopen = () => {
    status.textContent = "Connected.";
    sendButton.disabled = false;
};

socket.onmessage = event => {
    const data = JSON.parse(event.data);
    if (data.type === "history") data.messages.forEach(addMessage);
    if (data.type === "message") addMessage(data.message);
    if (data.type === "error") status.textContent = data.message;
};

socket.onclose = event => {
    sendButton.disabled = true;
    status.textContent = event.code === 4403
        ? "Chat access has ended. Check your login and course membership."
        : "Disconnected. Reconnect to load saved messages before sending again.";
    reconnectButton.hidden = false;
};

form.addEventListener("submit", event => {
    event.preventDefault();
    const body = input.value.trim();
    if (!body || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({body}));
    input.value = "";
    input.focus();
});

reconnectButton.addEventListener("click", () => window.location.reload());
window.addEventListener("pagehide", () => socket.close());
