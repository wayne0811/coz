const nem = require('nem-sdk').default;
const readline = require('readline');

const rl = readline.createInterface({
	input: process.stdin,
});

var lines = []

rl.on('line', (line) => {
	lines.push(line)
});

rl.on('close', () => {
	//console.error(`read ${lines.length} lines`)
	var [privkey, pubkey, msg] = lines;
	if (process.argv[2] === 'decrypt')
		ciphertext = nem.crypto.helpers.decode(privkey, pubkey, msg)
	else
		ciphertext = nem.crypto.helpers.encode(privkey, pubkey, msg)
	process.stdout.write(ciphertext)
});
