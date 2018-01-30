// Include the library
var nem = require("nem-sdk").default;
var fs = require("fs");
var jsonrpc = require('json-rpc-server-stream')();

// Create an NIS endpoint object
var endpoint = nem.model.objects.create("endpoint")(nem.model.nodes.defaultTestnet, nem.model.nodes.defaultPort);
//var endpoint =  nem.model.objects.create("endpoint")('http://23.228.67.85', nem.model.nodes.defaultPort);

// Default RPC responses
// Newline serves as JSON message terminator
var rpc_res = function(res, reply) {
	reply(null,res)
	jsonrpc.push('\n')
}
var rpc_err = function(err, reply) {
	console.error(err)
	reply(null, err)
	jsonrpc.push('\n')
}

jsonrpc.rpc.on('send-transfer-transaction', (params, reply) => {
	params = params.kwargs

	var common = nem.model.objects.create("common")("", params.privkey);

	// Create an object with parameters
	var transferTransaction = nem.model.objects.create("transferTransaction")(params.address, 0, params.message);

	if (params.recv_pubkey) {
		//transferTransaction.isEncrypted = true;
		transferTransaction.messageType = 2
		transferTransaction.recipientPublicKey = params.recv_pubkey;
	}

	// Prepare the above object
	var transactionEntity = nem.model.transactions.prepare("transferTransaction")(common, transferTransaction, nem.model.network.data.testnet.id)

	// Serialize transfer transaction and announce
	nem.model.transactions.send(common, transactionEntity, endpoint).then( (res) => rpc_res(res, reply), (err) => rpc_err(err, reply) );
});

jsonrpc.rpc.on('get-incoming-transactions', (params, reply) => {
	params = params.kwargs
	nem.com.requests.account.transactions.incoming(endpoint, params.address).then( (res) => rpc_res(res, reply), (err) => rpc_err(err, reply) );
});

jsonrpc.rpc.on('get-outgoing-transactions', (params, reply) => {
	params = params.kwargs
	nem.com.requests.account.transactions.outgoing(endpoint, params.address).then( (res) => rpc_res(res, reply), (err) => rpc_err(err, reply) );
});

jsonrpc.rpc.on('pubkey-to-address', (params, reply) => {
	params = params.kwargs
	addr = nem.model.address.toAddress(params.pubkey, nem.model.network.data.testnet.id)
	rpc_res(addr, reply);
});

jsonrpc.rpc.on('privkey-to-pubkey', (params, reply) => {
	params = params.kwargs
	keypair = nem.crypto.keyPair.create(params.privkey);
	pubkey = keypair.publicKey.toString();
	rpc_res(pubkey, reply);
});

process.stdin.pipe(jsonrpc).pipe(process.stdout)
