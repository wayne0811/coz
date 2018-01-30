# CoZ

A triple-entry accounting proof of concept that uses the NEM blockchain for timestamping and notarization, and IPFS for tamper-proof document storage and transport.
Built by Team CoZ, entrants to the [Global NEM Hackathon](https://hackathon.nem.io/) 2017-2018.

## Installation
Download the ZIP file from Releases page, extract it and execute `__main__.py`.
Alternatively, see [Building](#building).

Dependencies:
- Python 3
- PyQt5
- NodeJS
- a local IPFS gateway

Bundled libraries:
- Python
  - jsonrpyc
  - py-ipfs-api
  - pyaes
- NodeJS
  - json-rpc-server-stream
  - nem-sdk

## Building
Clone the repository  and run `prepare.sh` in a Linux shell.
This downloads the submodules and required NodeJS packages, and produces a "coz" folder and corresponding ZIP file just like the one this repository provides. 

Dependencies:
- npm
- p7zip

## Usage
1. Prepare 2 NEM Testnet accounts, ensure both accounts have outgoing transactions so that their public keys are available.
2. Start a local IPFS gateway that listens on localhost port 8080.
3. Run `python __main__.py` in a terminal. The main window is shown.
4. `Tools -> Address book`, enter the addresses of the 2 accounts with suitable aliases.
5. `File -> Load private key`, select the private key file of the first account. Set account label if desired.
6. On the Send tab, click `New...`. The New transaction dialog is shown.
   - Select the other Testnet account from the address book as recipient
   - Provide an invoice number (any string)
   - Provide an invoice file (any file, although CSV is assumed)
   - Attach any additional supporting documents for the invoice

   The supplied data is uploaded to the IPFS gateway under a single directory.
   The directory hash is sent to the recipient in the encrypted message field of a 0-amount transfer transaction.
   Uploaded files are encrypted with AES to reduce the risk of accidental exposure in case of leaked IPFS hashes.

7. Load the private key of the 2nd account.
8. On the Receive tab, click `Refresh`. Confirmed transactions are downloaded from the blockchain and invoice data is rebuilt by querying the IPFS gateway.
9. The receiver has the option to download invoice data to local disk, either all at one go or by selecting individual documents.
10. (Not implemented) Receiver has the option to accept or reject the received invoice. A NEM transaction is sent back to the first account to irrevocably indicate acceptance or rejection of the invoice content.

### Notes and limitations
- All debug info & exceptions are displayed in the terminal. Unhandled exceptions show up as a message box as well.
- A `.config` folder is created in the working directory for persistent data storage. Remove this folder to reset the application to its first-run state.
- For each transaction, the IPFS directory can be explored by pointing a web browser to `http://localhost:8080/ipfs/[IPFS hash]`
- The AES encryption key is randomly generated for every transaction, and is directly readable from the IPFS directory. A possible further approach is to encrypt this key using sender & recipients' private/public keys prior to uploading.
- Encryption/decryption routies are performed entirely in memory. Avoid sending large files of 100MB or above.

## Disclaimer
This is a proof of concept and is not suitable for production use.
No security or performance guarantees are made.
Do not load sensitive information into this application, as it may become publicly visible on the NEM Testnet.
