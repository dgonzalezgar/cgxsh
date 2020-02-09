# cgxsh (Preview)
[![image](https://img.shields.io/pypi/v/cgxsh.svg?color=blue)](https://pypi.org/project/cgxsh/)
[![image](https://img.shields.io/pypi/pyversions/cgxsh.svg)](https://pypi.org/project/cgxsh/)
[![Downloads](https://pepy.tech/badge/cgxsh)](https://pepy.tech/project/cgxsh)
[![License: MIT](https://img.shields.io/pypi/l/cgxsh.svg?color=brightgreen)](https://pypi.org/project/cgxsh/)
[![GitHub issues open](https://img.shields.io/github/issues/ebob9/cgxsh.svg)](https://github.com/ebob9/cgxsh/issues)

**C**loud**G**eni**X** **SH**ell (`cgxsh`)

Command-line access to the controller-based CloudGenix ION Troubleshooting Toolkit.

#### Synopsis
The `cgxsh` application is designed to allow a CloudGenix customer to replace a lot of the device-specific troubleshooting 
traditionally performed via SSH with a cloud-based connectivity model.

This utility attempts to behave "ssh-like", but there are fundamental differences.

This utility should support Windows (Win 10 or higher) and Mac/Linux systems.

#### Requirements
* Active CloudGenix Account
* Python >=3.6
* CloudGenix IONs running 5.2.1+ Software
* Python modules:
    * cloudgenix   - <https://github.com/CloudGenix/sdk-python>
    * websockets   - <https://websockets.readthedocs.io/en/stable/>
    * fuzzywuzzy   - <https://github.com/seatgeek/fuzzywuzzy/>
    * pyyaml       - <https://pyyaml.org/wiki/PyYAMLDocumentation>
    * tabulate     - <https://github.com/astanin/python-tabulate>
    * cryptography - <https://github.com/pyca/cryptography>

#### Installation
* Via PIP as simple as `pip install cgxsh`

#### Commands/Features

##### cgxsh
* SSH-replacement console utility using CloudGenix Cloud Controller
* Simple commandline use: `cgxsh "Portland ION"`
* Interactive session by default, but specific commands and exit support too: `cgxsh "Portland ION" "set paging off" "dump lldp all"`
* Multi-tenant ESP/MSP support: `cgxsh "Device_name"@"Tenant_Name"`
* Configuration file with Multi-tenant support and optional Encryption to store credential(s)
* Fuzzy matching: 
    ```shell script
    edwards-mbp-pro:cgxsh aaron$ cgxsh "Portland ION"
    No match for Portland ION, best guesses:
      1) Portland Sales Office ION, (86%)
      2) ION2K-A, (54%)
      3) ION2K-B, (54%)
      4) DHL-1, (36%)
      5) MAD-7K-1, (36%)
      6) MAD-7K-2, (36%)
      7) MAN-3K-1, (36%)
    Select a number, or any other key to exit: 1
    ```
* Escape command menu for operations while connected: 
    ```text
    Portland Sales Office ION#  
    
    cgxsh> ?
    Commands are:
        send            Send special characters (help send for more)
        sdkdebug        Enable/Disable API/WebSocket debug messages (help sdkdebug for more)
        verbosity       Change cgxsh message verbosity (help verbosity for more)
        sessions        View active Toolkit Websocket Sessions (help sessions for more)
        sessions_kill   View and kill/close active Toolkit Websocket Sessions (help sessions_kill for more)
        quit            Close the connection and exit.
        close           Close the connection and exit.
        exit            Close the connection and exit.
        help            Additional help on sub commands. eg: help <command>
        
        Pressing <enter> on empty command line will return you to session.
        
    cgxsh> 
    ```
##### cgxsh_generic_ws
* Generic CloudGenix Websocket client to manage and experiment with Subscriptions.
* CloudGenix-required keepalive handling
* JSON output formatting.

##### cgxsh_create_defaultconfig
* Creates default cgxsh config (in $HOME/.cgxsh/config.yml)

##### cgxsh_edit_config
* Launches editor to edit `cgxsh` config.
    * Mac/Linux: Default /usr/bin/vi
    * Windows: Default notepad.exe
* Handles decryption/re-encryption of configuration, if encrypted.

##### cgxsh_decrypt_config
* Allows for decryption `cgxsh` configuration, if desired.

##### cgxsh_encrypt_config
* Encrypts `cgxsh` configuration, if not already encrypted.

#### License
MIT

#### Version
| Version | Build | Changes |
| ------- | ----- | ------- |
| **1.0.0** | **b1** | Initial Release |
| **0.0.1** | **b1** | Placeholder for future release. |

#### (Optional) Environment Variables
* `AUTH_TOKEN` or `X_AUTH_TOKEN`: CloudGenix Controller Authentication Token (overrides configuration files)
* `CGXSH_CONFIG_PASSWORD`: Password for loading encrypted `cgxsh` configuration.

#### Usage info and examples.
##### Connecting to an ION with fuzzy name match and no configuration info saved
`cgxsh \<ION name or ID>`
```text
edwards-mbp-pro:cgxsh aaron$ cgxsh "Portland ION"
controller login: user@email.com
controller password: 

No match for Portland ION, best guesses:
  1) Portland Sales Office ION, (86%)
  2) ION2K-A, (54%)
  3) ION2K-B, (54%)
  4) MAN-3K-1, (36%)
  5) MAD-7K-2, (36%)
  6) MAD-7K-1, (36%)
  7) DHL-1, (36%)
Select a number, or any other key to exit: 1
Connecting to Portland Sales Office ION (15608897741660166).
Connected to 15608897741660166.
Escape character is '^]'.
ec2683ee-0d9c-8a64-3467-55121bb8a672 login: aaron
Password: 
Last login: Tue Dec 17 22:47:18 UTC 2019 on pts/0
 
Portland Sales Office ION# dump standingalarms 

Code		:	NETWORK_VPNPEER_UNREACHABLE
Ident		:	15608901339660208
Severity	:	minor
Raised		:	2019-12-12 20:54:44.834 +0000 UTC (122h6m8.469335222s ago)
Correlation ID	:	F70lP6T9
 vpn_link_id	:	15608901339570207
 al_id		:	15608896659530120

Portland Sales Office ION#  
```

##### Connecting to an ION with exact name match and controller/device configuration in config file
`cgxsh \<ION name or ID>`
```text
edwards-mbp-pro:cgxsh aaron$ cgxsh "Portland Sales Office ION"
Connecting to Portland Sales Office ION (15608897741660166).
Connected to 15608897741660166.
Escape character is '^]'.

Last login: Tue Dec 17 22:52:46 UTC 2019 on pts/0
 
Portland Sales Office ION# dump standingalarms

Code		:	NETWORK_VPNPEER_UNREACHABLE
Ident		:	15608901339660208
Severity	:	minor
Raised		:	2019-12-12 20:54:44.834 +0000 UTC (122h6m8.469335222s ago)
Correlation ID	:	F70lP6T9
 vpn_link_id	:	15608901339570207
 al_id		:	15608896659530120

Portland Sales Office ION#  
```

##### Connecting to an ION on a sub-tenant via an ESP/MSP account with saved per-sub-tenant configurations
`cgxsh \<ION name or ID>`
```text
edwards-mbp-pro:cgxsh aaron$ cgxsh "Portland Sales Office ION"@MyCustomerClientZ 
No match for MyCustomerClientZ, best guesses:
  1) MyCustomerClientA, (90%)
  2) CustomerClientB, (22%)
  3) CustomerClientC, (22%)
  4) CustomerClientD, (22%)
  5) CustomerClientE, (22%)
  6) CustomerClientF, (22%)
Select a number, or any other key to exit: 1

Connecting to Client MyCustomerClientA (MyCustomerClient_canonicalname).
Connecting to Portland Sales Office ION (15608897741660166).
Connected to 15608897741660166.
Escape character is '^]'.

Last login: Tue Dec 17 22:52:46 UTC 2019 on pts/0
 
Portland Sales Office ION# dump standingalarms

Code		:	NETWORK_VPNPEER_UNREACHABLE
Ident		:	15608901339660208
Severity	:	minor
Raised		:	2019-12-12 20:54:44.834 +0000 UTC (122h6m8.469335222s ago)
Correlation ID	:	F70lP6T9
 vpn_link_id	:	15608901339570207
 al_id		:	15608896659530120

Portland Sales Office ION#  
```

##### Managing connected cgxsh/web toolkit users to the current ION
`Press escape char (CTRL-]) during cgxsh session`
```text
Portland Sales Office ION#  

cgxsh> ?
Commands are:
    send            Send special characters (help send for more)
    sdkdebug        Enable/Disable API/WebSocket debug messages (help sdkdebug for more)
    verbosity       Change cgxsh message verbosity (help verbosity for more)
    sessions        View active Toolkit Websocket Sessions (help sessions for more)
    sessions_kill   View and kill/close active Toolkit Websocket Sessions (help sessions_kill for more)
    quit            Close the connection and exit.
    close           Close the connection and exit.
    exit            Close the connection and exit.
    help            Additional help on sub commands. eg: help <command>
    
    Pressing <enter> on empty command line will return you to session.
    
cgxsh> sessions_kill element
Toolkit Sessions:
  Index  Element                    Operator                  Age       State                                  Session ID
-------  -------------------------  ------------------------  --------  -------  ----------------------------------------
      1  Portland Sales Office ION  aaron@cloudgenix.com      1h36m12s  active   1576618422757015099992703857847609972162
      2  Portland Sales Office ION  otheruser@cloudgenix.com  9m9s      active   1576623645452007700007702497325448497534
Total: 2
Enter Index to remove (range for multiple (eg. 1,3,5-10), or x to exit: 2
Planning to end the following sessions (index): 2.
Confirm? (y/n): y
Ended session 2 to Portland Sales Office ION.

cgxsh> 
Portland Sales Office ION# 
```

##### Encrypting a clear-text configuration.
```shell script
edwards-mbp-pro:cgxsh aaron$ cgxsh_encrypt_config 
Enter password to encrypt file: 
Confirm file encryption password: 
Saving encrypted configuration: Done.
edwards-mbp-pro:cgxsh aaron$ 
```

##### Default config.yml template
    ---
    type: cgxsh
    version: 1.0
    
    # This section allows you to specify a default AUTH_TOKEN, DEVICE_USER and DEVICE_PASSWORD. These will be used
    # by default if others are not specified.
    #
    # For Controller authentication, AUTH_TOKEN is used first (if present.) If no AUTH_TOKEN, CONTROLLER_USER and 
    # CONTROLLER_PASSWORD are used. If those are missing or fail, login will be prompted.
    # 
    # If the DEVICE_USER or DEVICE_PASSWORD fails, you will be prompted to finish logging in when connecting to the device.
    
    DEFAULT:
        AUTH_TOKEN:
        CONTROLLER_USER:
        CONTROLLER_PASSWORD:
        DEVICE_USER: 
        DEVICE_PASSWORD: 
    
    # If you have a CloudGenix MSP/ESP portal account, you can specify the device access credentials on a per-client
    # basis. If the client name is not an exact match, the credentials will not be used.
    #
    # Note: MSP/ESP client attachment requires DEFAULT: CONTROLLER_USERNAME/CONTROLLER_PASSOWRD. AUTH_TOKENs cannot be used. 
    
    ESP:
      "Example Client1 Name Match":
        DEVICE_USER:
        DEVICE_PASSWORD: 
        
      "Example Client2 Name Match":
        DEVICE_USER:
        DEVICE_PASSWORD: 

##### Subscribe to generic websocket to get push config change messages (element, site in this example)
`cgxsh_generic_ws`
```text
edwards-mbp-pro:cgxsh aaron$ cgxsh_generic_ws
Connected.
> { "type": "PUT", "uri": "/v2.0/api/tenants/10006/subscriptions", "body": {"type": "config_change", "subscriptions": [{"resource_key": "elements"},{"resource_key": "sites"}] }}
< {
      "type": "PUT",
      "uri": "/v2.0/api/tenants/10006/subscriptions",
      "body": {
          "id": "15766253860930016",
          "_etag": 1,
          "_content_length": 0,
          "_schema": 0,
          "_created_on_utc": 15766253860930016,
          "_updated_on_utc": 15766253860930016,
          "_status_code": "200",
          "_message_id": "1576625386053000499998772050152704482435",
          "_request_id": "1576625386053000399991149536419934892671",
          "subscriptions": [
              {
                  "resource_key": "elements"
              },
              {
                  "resource_key": "sites"
              }
          ],
          "type": "config_change"
      }
  }
```

`subsequent time later when configuration change on element occurs..`
```text
< {
      "id": "15766254376560072",
      "_created_on_utc": 15766254376560072,
      "_updated_on_utc": 15766254376560072,
      "_message_id": "1576625437641018399996760510275758800343",
      "_request_id": "1576625437641018299992839389780516744938",
      "operator_id": "15713488339050031",
      "operator_tenant_id": "10006",
      "esp_tenant_id": "123",
      "request_id": "1576625437588017700003942214959372913327",
      "source_ip": "96.64.220.253",
      "resource_key": "elements",
      "resource_id": "15608897741660166",
      "resource_etag": 1728,
      "resource_version": "v2.3",
      "request_type": "PUT",
      "request_uri": "/v2.3/api/tenants/10006/elements/15608897741660166",
      "request_body": {
          "_etag": 1727,
          "_schema": 0,
          "id": "15608897741660166",
          "site_id": "15608896590040129",
          "name": "Portland Sales Office ION",
          "description": null,
          "tags": [
              "SNOW-high"
          ],
          "sw_obj": null,
          "cluster_insertion_mode": null,
          "cluster_member_id": null,
          "l3_direct_private_wan_forwarding": true,
          "l3_lan_forwarding": true,
          "vpn_to_vpn_forwarding": false,
          "network_policysetstack_id": null,
          "priority_policysetstack_id": null,
          "nat_policysetstack_id": null,
          "spoke_ha_config": null
      },
      "response_code": 200,
      "response_body": {
          "id": "15608897741660166",
          "_etag": 1728,
          "_content_length": "0",
          "_schema": 0,
          "_created_on_utc": 15608897741660166,
          "_updated_on_utc": 15766254376080179,
          "_status_code": "200",
          "_request_id": "1576625437588017700003942214959372913327",
          "_debug": null,
          "_info": null,
          "_warning": null,
          "_error": null,
          "tenant_id": "10006",
          "site_id": "15608896590040129",
          "software_version": "5.2.1-a85",
          "hw_id": "ec2683ee-0d9c-8a64-3467-55121bb8a672",
          "serial_number": "ec2683ee-0d9c-8a64-3467-55121bb8a672",
          "model_name": "ion 3102v",
          "name": "Portland Sales Office ION",
          "description": null,
          "role": "SPOKE",
          "state": "bound",
          "allowed_roles": [
              "HUB",
              "SPOKE"
          ],
          "cluster_insertion_mode": null,
          "cluster_member_id": null,
          "l3_direct_private_wan_forwarding": true,
          "l3_lan_forwarding": true,
          "connected": true,
          "admin_action": null,
          "deployment_op": null,
          "network_policysetstack_id": null,
          "priority_policysetstack_id": null,
          "spoke_ha_config": null,
          "tags": [
              "SNOW-high"
          ],
          "nat_policysetstack_id": null,
          "vpn_to_vpn_forwarding": false
      },
      "time_ms": 52,
      "request_content_length": 439,
      "response_content_length": 0,
      "request_ts": 1576625437588,
      "response_ts": 1576625437640
  }
> 
```



#### Command-line arguments

##### cgxsh
```text
usage: cgxsh [-h] [--controller-email CONTROLLER_EMAIL]
             [--controller-password CONTROLLER_PASSWORD]
             [--device-user DEVICE_USER] [--device-password DEVICE_PASSWORD]
             [--noexit] [--controller CONTROLLER] [--insecure] [--noregion]
             [--override-host-header FORCE_HOST] [--verbosity VERBOSITY]
             [--sdkdebug SDKDEBUG]
             element[@client] ...

cgxsh (1.0.0b1)

optional arguments:
  -h, --help            show this help message and exit

cgxsh_args:
  CGXSH Arguments

  --controller-email CONTROLLER_EMAIL, -E CONTROLLER_EMAIL
                        Use this email for controller login.
  --controller-password CONTROLLER_PASSWORD
                        Use this password for controller login. NOT
                        RECOMMENDED - Password will likely be stored in shell
                        history.
  --device-user DEVICE_USER
                        Use this user to login to the Element Toolkit.
  --device-password DEVICE_PASSWORD
                        Use this password to login to the Element Toolkit. NOT
                        RECOMMENDED - Password will likely be stored in shell
                        history.
  --noexit              If using commands, do not exit after running commands.
                        Maintain interactive shell.
  element[@client]      Element name or ID to connect to. If connecting as
                        ESP/MSP account, @client name or ID is required.
  commands              (Optional) Strings of space-separated Toolkit commands
                        to run. Example: "set paging off" "dump lldp all"

Controller Options:
  These options change how the program connects to the CloudGenix Controller

  --controller CONTROLLER, -C CONTROLLER
                        Override Controller API URI. Default:
                        https://api.elcapitan.cloudgenix.com
  --insecure, -I        Do not verify API SSL certificate
  --noregion, -NR       Ignore Region-based redirection.
  --override-host-header FORCE_HOST, -OH FORCE_HOST
                        Force Host Header on API requests.

Debug:
  These options enable debugging output

  --verbosity VERBOSITY, -V VERBOSITY
                        CGXSH client verbosity.
  --sdkdebug SDKDEBUG, -D SDKDEBUG
                        Enable CloudGenix SDK Debug output, levels 0-3
```

##### cgxsh_generic_ws
```text
usage: cgxsh_generic_ws [-h] [--no-format] [--show-keepalives]
                        [--controller-email CONTROLLER_EMAIL]
                        [--controller-password CONTROLLER_PASSWORD]
                        [--controller CONTROLLER] [--insecure] [--noregion]
                        [--override-host-header FORCE_HOST]
                        [--verbosity VERBOSITY] [--sdkdebug SDKDEBUG]
                        [[@client]]

cgxsh_generic_ws (1.0.0b1)

optional arguments:
  -h, --help            show this help message and exit

cgxsh_generic_ws args:
  CGXSH Generic WebSocket Client Arguments

  --no-format, -NF      Disable output pretty-printing/formatting.
  --show-keepalives     Show background keepalive messages
  --controller-email CONTROLLER_EMAIL, -E CONTROLLER_EMAIL
                        Use this email for controller login.
  --controller-password CONTROLLER_PASSWORD
                        Use this password for controller login. NOT
                        RECOMMENDED - Password will likely be stored in shell
                        history.
  [@client]             If connecting as ESP/MSP account, @client name or ID
                        is required.

Controller Options:
  These options change how the program connects to the CloudGenix Controller

  --controller CONTROLLER, -C CONTROLLER
                        Override Controller API URI. Default:
                        https://api.elcapitan.cloudgenix.com
  --insecure, -I        Do not verify API SSL certificate
  --noregion, -NR       Ignore Region-based redirection.
  --override-host-header FORCE_HOST, -OH FORCE_HOST
                        Force Host Header on API requests.

Debug:
  These options enable debugging output

  --verbosity VERBOSITY, -V VERBOSITY
                        CGXSH Generic WebSocket Client verbosity.
  --sdkdebug SDKDEBUG, -D SDKDEBUG
                        Enable CloudGenix SDK Debug output, levels 0-3
```

##### cgxsh_edit_config
```text
usage: cgxsh_edit_config [-h] [--editor EDITOR]

cgxsh_edit_config (1.0.0b1)

optional arguments:
  -h, --help            show this help message and exit

cgxsh_edit_config:
  CGXSH Edit Configuration Arguments

  --editor EDITOR, -E EDITOR
                        Use this program to edit configuration. Editor must
                        supportfilename as first argument. Default:
                        /usr/bin/vi
```

##### cgxsh_edit_config
```text
usage: cgxsh_decrypt_config [-h] [--force FORCE]

cgxsh_decrypt_config (1.0.0b1)

optional arguments:
  -h, --help            show this help message and exit

cgxsh_decrypt_config:
  CGXSH Decrypt Configuration Arguments

  --force FORCE, -F FORCE
                        Export configurations to alternate file. Don't verify
                        contents after decryption. Must specify filename to
                        decrypt contents into, since config may be corrupt.
                        Valid password is still required.
```