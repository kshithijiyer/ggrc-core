/*
 Copyright (C) 2018 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import * as StateUtils from '../../plugins/utils/state-utils';
import router from '../../router';

let viewModel = can.Map.extend({
  disabled: false,
  options: {
    name: 'status',
    query: null,
  },
  filterStates: [],
  widgetId: null,
  modelName: null,
  displayPrefs: null,
  initializeFilter(states) {
    let statuses = this.attr('filterStates');
    statuses.forEach((item) => {
      item.attr('checked', (states.indexOf(item.value) > -1));
    });
    this.setFilter(states);
  },
  getDefaultStates() {
    let widgetId = this.attr('widgetId');
    // Get the status list from local storage
    let savedStates = this.attr('displayPrefs').getTreeViewStates(widgetId);
    // Get the status list from query string
    let queryStates = router.attr('state');

    let modelName = this.attr('modelName');
    let allStates = StateUtils.getStatesForModel(modelName);
    let defaultStates = (queryStates || savedStates).filter((state) => {
      return allStates.includes(state);
    });

    if (defaultStates.length === 0) {
      defaultStates = StateUtils.getDefaultStatesForModel(modelName);
    }

    return defaultStates;
  },
  saveTreeStates(selectedStates) {
    this.setFilter(selectedStates);

    let widgetId = this.attr('widgetId');
    this.attr('displayPrefs').setTreeViewStates(widgetId, selectedStates);
  },
  setFilter(selected) {
    let statuses = this.attr('filterStates');
    let query = null;

    if (selected.length && statuses.length !== selected.length) {
      query = StateUtils.buildStatusFilter(selected, this.attr('modelName'));
      router.attr('state', selected);
    } else {
      router.removeAttr('state');
    }

    this.attr('options.query', query);
  },
});

export default can.Component.extend({
  tag: 'tree-status-filter',
  viewModel: viewModel,
  events: {
    inserted() {
      let vm = this.viewModel;

      let filterStates = StateUtils.getStatesForModel(vm.attr('modelName'))
        .map((state) => {
          return {
            value: state,
          };
        });

      if (vm.registerFilter) {
        let options = vm.attr('options');
        vm.registerFilter(options);
      }

      vm.attr('filterStates', filterStates);

      CMS.Models.DisplayPrefs.getSingleton().then((displayPrefs) => {
        vm.attr('displayPrefs', displayPrefs);

        let defaultStates = vm.getDefaultStates();
        vm.initializeFilter(defaultStates);

        // Start listening route events only after full initialization.
        vm.attr('router', router);
      });
    },
    'multiselect-dropdown multiselect:closed'(el, ev, selected) {
      ev.stopPropagation();
      let selectedStates = selected.map((state) => state.value);

      this.viewModel.saveTreeStates(selectedStates);
    },
    '{viewModel} disabled'() {
      if (this.viewModel.attr('disabled')) {
        this.viewModel.initializeFilter([]);
      } else {
        let defaultStates = this.viewModel.getDefaultStates();
        this.viewModel.initializeFilter(defaultStates);
      }
    },
    '{viewModel.router} state'(router, event, newValue) {
      if (!this.viewModel.attr('disabled')) {
        let states = newValue ||
        this.viewModel.attr('filterStates').map((state) => state.value);

        this.viewModel.initializeFilter(states);
        this.viewModel.dispatch('filter');
      }
    },
  },
});
