# abscomp
Compare 2 Audiobookshelf libraries and output various json and csv files showing the difference.

### Requirements
- python 3.11+
- requests 2.31+
- rich 13.7+
- typer 0.9.0+

### Configure
- a url, token, and library id for both libraries
- details can be found in the config file

##### absconfig.toml
- edit the file, enter the 3 detail fields for both libraries
- do not modify anything outside of the 6 "quote" fields

### Execute
```bash
python abscomp.py
```
To specify a config file: (note: the format inside the file must be the same)
```bash
python abscomp.py /home/me/Documents/my-absconfig.toml
```

### Output

By default, this will just output a summary to the console.
For more details, add "-c" for csv and/or "-j" for json text file output.
