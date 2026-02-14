install_data(
  'com.github.bearenbey.Gmpv.desktop',
  install_dir: get_option('datadir') / 'applications',
)

install_data(
  'com.github.bearenbey.Gmpv.metainfo.xml',
  install_dir: get_option('datadir') / 'metainfo',
)

icon_sizes = ['48', '128', '256', '512']

foreach size : icon_sizes
  install_data(
    'icons' / 'com.github.bearenbey.Gmpv-@0@.png'.format(size),
    rename: 'com.github.bearenbey.Gmpv.png',
    install_dir: get_option('datadir') / 'icons' / 'hicolor' / '@0@x@0@'.format(size) / 'apps',
  )
endforeach
