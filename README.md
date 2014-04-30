# parser.theyworkforyou.com

This site holds information about the parser that powers TheyWorkForYou, Public
Whip, and more.

## This Site

### Compiling

This site is mostly compiled by magic (specifically
[Jekyll](http://jekyllrb.com/) and [Sass](http://sass-lang.com/), which will
have to be installed before you can do anything. The following commands will
install the necessary software:

* `gem install --no-document --user-install github-pages` for preference, or
  (if you have an older version of Ruby) `jekyll`
* `gem install --no-document --user-install sass`

You may find the following commands useful:

* `jekyll serve --watch` - Starts a web server on `localhost:4000` with the
  latest compiled copy of the site. Recompiles when files change.
* `sass --watch` - Monitors static asset folders for changes, and recompiles
  when necessary.
