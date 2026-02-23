This will like use curl and pup to check what is available on a webiste for download and then its gonna use something like pygame to let you surf the download links with a controller and then use wget on those links.

The files should not be placed in downloads, but configured to drop in a certain directory with a config json or something like that.
The config should also let you optionally choose to automatically unzip a zip file and then delete the artifact. This should be configurable and not on by default.

So the workflow would be like:

pup https://example.com/downloads
surf with controller
wget https://example.com/downloads/file.zip
Process the file as decided by the config.
