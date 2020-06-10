# Settings configuration

In order to run the tool, you need to create a file _settings.json_ in this directory, based on [_settings.json.example_](https://github.com/JetBrains-Research/code-change-miner/blob/master/conf/settings.json.example).
Here are the detailed explanations of the settings:

### Settings for the _collect-cgs_ mode:

Name                             | Description
---                              | ---
**gumtree_bin_path**             | path to GumTree binary file
**git_repositories_dir**         | path to the directory with Git repositories
**traverse_file_max_line_count** | the maximum number of lines in the analyzed files (processing larger files may sometimes cause memory issues)
**traverse_async**               | **true** for the asynchronous processing of repositories
**traverse_min_date**            | **(optional)** the date in the **%d.%m.%Y** format, no changes older than this date will be processed
**change_graphs_storage_dir**    | path to the output directory
**change_graphs_store_interval** | batch size of the number of change graphs to be saved in a single file (to prevent the files from getting too big)

### Settings for the _patterns_ mode:

By default, the input for mining patterns is the output of collecting change graphs, so this step should be run after the previous one.

Name                                   | Description
---                                    | ---
**patterns_output_dir**                | path to the output directory (in order to correctly visualize the results, this directory must be located [here](https://github.com/JetBrains-Research/code-change-miner/tree/master/output) or have all the same files in the parent directory)
**patterns_output_details**            | **true** for saving a JSON for each pattern instance with its details:  repository name, commit hash, contacts of the author, and the names of the functions (please note that if you want such information for all the instances, you also need to switch **patterns_full_print** to **true**)
**patterns_min_frequency**             | minimum frequency of the changes graph repetition to be considered a pattern 
**patterns_max_frequency**             | frequency of the changes graph repetition for the pattern to be considered _common_ (for such patterns, some instances are ignored for optimization purposes)
**patterns_async_mining**              | **true** for the asynchronous mining of patterns **(not recommended)**
**patterns_full_print**                | **true** for saving the information about every individual instance of a pattern, **false** for saving one instance per pattern
**patterns_hide_overlapped_fragments** | **true** for ignoring pattern instances with overlapping code fragments
**patterns_min_size**                  | minimum number of nodes that the pattern must have to be included in the output
**patterns_min_date**                  | **(optional)** the date in the **%d.%m.%Y** format, no changes older than this date will be processed

### Additional settings:

Name                        | Description
---                         | ---
**logger_file_path**        | path to the log output file
**logger_file_log_level**   | log level to be saved into the log file, possible values: **ERROR**, **WARNING**, **INFO**, **DEBUG**
**logger_stdout_log_level** | log level to be printed into the console, possible values: **ERROR**, **WARNING**, **INFO**, **DEBUG**


