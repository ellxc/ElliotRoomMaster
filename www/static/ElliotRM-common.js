function setupMQTT() {
    const client = new Paho.Client(location.hostname, 8080, "clientId");
    client.connect({onSuccess: onConnect});
    client.onMessageArrived = onMessageArrived;

    // called when the client connects
    function onConnect() {
        // Once a connection has been made, make a subscription and send a message.
        console.log("onConnect");
    }

    // called when a message arrives
    function onMessageArrived(message) {
        console.log("onMessageArrived:" + message.payloadString);
        EventBus.dispatch(message.destinationName, this, message)
    }

    function setupListener(topic, func) {
        EventBus.addEventListener(topic, func);
        client.subscribe(topic);
    }
}