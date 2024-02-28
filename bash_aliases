# Create a symlink to this file in ~/.bash_aliases using:
#   ln -s ~/simoc-sam/bash_aliases ~/.bash_aliases


# ls aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'

# used to activate the venv
alias activate='source venv/bin/activate'

# run a simoc-sam.py command directly in the venv
alias sam='$(which ~/simoc-sam/venv/bin/python || which python3) ~/simoc-sam/simoc-sam.py'
