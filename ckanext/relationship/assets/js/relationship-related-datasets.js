(function () {
  'use strict';

  function parseDatasetIds(rawValue) {
    if (!rawValue) {
      return [];
    }

    if (Array.isArray(rawValue)) {
      return rawValue;
    }

    try {
      var parsed = JSON.parse(rawValue);
      if (Array.isArray(parsed)) {
        return parsed;
      }
    } catch (e) {
      // fallback below
    }

    return String(rawValue)
      .split(',')
      .map(function (item) {
        return item.trim().replace(/^["']|["']$/g, '');
      })
      .filter(Boolean);
  }

  $(document).on('click', '.load-related-datasets', function () {
    var button = $(this);
    var block = button.closest('.related-datasets-block');
    var list = block.find('.related-datasets-list');

    if (block.data('loaded')) {
      list.toggle();

      if (list.is(':visible')) {
        button.text('Hide related datasets');
      } else {
        button.text('Show related datasets');
      }

      return;
    }

    var datasetIds = parseDatasetIds(block.attr('data-related-dataset-ids'));

    if (!datasetIds.length) {
      button.text('No related datasets');
      return;
    }

    button.prop('disabled', true).text('Loading related datasets...');

    $.ajax({
      url: '/api/3/action/relationship_related_datasets_for_molecule',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        dataset_ids: datasetIds
      }),
      success: function (response) {
        list.empty();

        if (!response.success || !response.result || !response.result.length) {
          list.append($('<li>').text('No related datasets found.'));
        } else {
          response.result.forEach(function (dataset) {
            list.append(
              $('<li>').append(
                $('<a>', {
                  href: dataset.url,
                  text: dataset.title || dataset.name || dataset.id
                })
              )
            );
          });
        }

        list.show();
        block.data('loaded', true);
        button.prop('disabled', false).text('Hide related datasets');
      },
      error: function (xhr) {
        console.error(xhr);
        button.prop('disabled', false).text('Could not load. Try again.');
      }
    });
  });
})();