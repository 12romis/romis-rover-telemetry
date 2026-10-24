/*
 * Малювання графіків дашборду на закріпленому ECharts (ADR-0002).
 *
 * Скрипт «німий»: усі числа, причини відсутності й підписи приходять у даних блока
 * (`<script type="application/json" id="chart-data-<блок>">`), а доменні константи — у
 * `data.constants`. Нуль не підставляється замість відсутнього значення (конституція №4).
 * Жодної розмітки зі звітних рядків: підказка збирається через createElement/textContent.
 */
(function () {
  'use strict';

  var UNAVAILABLE =
    'Графік тимчасово недоступний. Решта сторінки працює — спробуйте оновити сторінку трохи пізніше.';
  var NO_DATA = 'немає даних';
  var GAP_LABEL = 'не дійшла';
  var AXIS_NAME = 'Номер сесії';
  var AXIS_PADDING = 0.4; // запас осі напруги над і під опорними лініями, В
  var MARKER_RADIUS = 4.5;
  var MARKER_SHIFT = 10; // зсув маркерів початку й кінця від центра слота, px

  var charts = [];

  // ---------- Допоміжне ----------

  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function comma(value, digits) {
    return value.toFixed(digits).replace('.', ',');
  }

  function node(tag, text, className) {
    var element = document.createElement(tag);
    if (text !== undefined) {
      element.textContent = text;
    }
    if (className) {
      element.className = className;
    }
    return element;
  }

  function categories(data) {
    return data.slots.map(function (slot) {
      return String(slot.seq);
    });
  }

  // Причина відсутнього значення за seq і назвою значення (текст готує сервер).
  function reasonFor(data, seq, value) {
    for (var i = 0; i < data.reasons.length; i++) {
      var r = data.reasons[i];
      if (r.seq === seq && r.value === value) {
        return r.label;
      }
    }
    return '';
  }

  // ---------- Підказка (SCR-05) ----------

  // Рядок «підпис — значення»; відсутнє: підпис + курсив «немає даних» + повна причина.
  function row(label, text, reason) {
    var line = node('div', undefined, 'chart-tip__row');
    if (text !== null) {
      line.textContent = label + ' — ' + text;
      return line;
    }
    line.appendChild(document.createTextNode(label + ' — '));
    line.appendChild(node('em', NO_DATA));
    if (reason) {
      line.appendChild(document.createTextNode(' (' + reason + ')'));
    }
    return line;
  }

  function tooltipFor(data, index, rows) {
    var slot = data.slots[index];
    var box = node('div', undefined, 'chart-tip');
    box.appendChild(node('strong', 'Виїзд № ' + slot.seq));
    box.appendChild(node('div', 'Отримано (за київським часом): ' + slot.received));
    rows.forEach(function (r) {
      box.appendChild(r);
    });
    return box;
  }

  // Підказка слота; слот «не дійшла» підказки не має.
  function tooltipOption(data, rowsFor) {
    return {
      trigger: 'axis',
      confine: true,
      className: 'chart-tip-box',
      triggerOn: 'mousemove|click',
      axisPointer: { type: 'shadow' },
      formatter: function (params) {
        var list = Array.isArray(params) ? params : [params];
        if (!list.length) {
          return '';
        }
        var index = list[0].dataIndex;
        if (data.slots[index].gap) {
          return '';
        }
        return tooltipFor(data, index, rowsFor(index));
      },
    };
  }

  // ---------- Спільна вісь ----------

  // Слот «не дійшла»: штрихова рамка на всю ширину своєї категорії з підписом уздовж слота.
  function gapSeries(data) {
    var indexes = [];
    data.slots.forEach(function (slot, i) {
      if (slot.gap) {
        indexes.push([i]);
      }
    });
    return {
      type: 'custom',
      name: 'Сесія не дійшла',
      silent: true,
      data: indexes,
      encode: { x: 0 },
      renderItem: function (params, api) {
        var area = params.coordSys;
        var width = api.size([1, 0])[0];
        var center = api.coord([api.value(0), 0])[0];
        return {
          type: 'group',
          children: [
            {
              type: 'rect',
              shape: { x: center - width / 2 + 1, y: area.y, width: width - 2, height: area.height },
              style: { fill: 'none', stroke: token('--chart-gap'), lineDash: [4, 3], lineWidth: 1 },
            },
            {
              type: 'text',
              x: center,
              y: area.y + area.height / 2,
              rotation: Math.PI / 2,
              style: {
                text: GAP_LABEL,
                x: 0,
                y: 0,
                align: 'center',
                verticalAlign: 'middle',
                fontSize: 12,
                fill: token('--chart-gap'),
              },
            },
          ],
        };
      },
    };
  }

  // Числа осі з комою, як у решті інтерфейсу.
  function axisNumber(value) {
    return String(Math.round(value * 100) / 100).replace('.', ',');
  }

  function xAxis(data) {
    return {
      type: 'category',
      data: categories(data),
      name: AXIS_NAME,
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: { color: token('--color-muted') },
      axisLabel: { color: token('--color-muted') },
      axisTick: { alignWithLabel: true },
    };
  }

  // Порожня серія: несе лише опорні лінії; значень не має (null, не нуль).
  function frameSeries(data, markLine) {
    return {
      type: 'line',
      silent: true,
      symbol: 'none',
      lineStyle: { width: 0 },
      data: data.slots.map(function () {
        return null;
      }),
      markLine: markLine,
    };
  }

  // Лишається в кожного слота виїзду: підказка спрацьовує й тоді, коли всі значення слота null.
  function hitSeries(data) {
    return {
      type: 'custom',
      name: '',
      silent: true,
      data: data.slots.map(function (slot, i) {
        return [i, null];
      }),
      encode: { x: 0, y: 1 },
      renderItem: function () {
        return null;
      },
    };
  }

  function mount(section, name, option) {
    var element = section.querySelector('[data-chart="' + name + '"]');
    if (!element) {
      throw new Error('chart element missing');
    }
    element.hidden = false;
    element.textContent = '';
    var chart = echarts.init(element, null, { renderer: 'canvas' });
    chart.setOption(option);
    charts.push({ chart: chart, element: element });
  }

  // ---------- Блок «Акумулятор» ----------

  function marker(shape, color, shift) {
    return function (params, api) {
      var value = api.value(1);
      if (value === null || value === undefined) {
        return null;
      }
      var point = api.coord([api.value(0), value]);
      var x = point[0] + shift;
      var y = point[1];
      var style = { fill: color };
      if (shape === 'circle') {
        return { type: 'circle', shape: { cx: x, cy: y, r: MARKER_RADIUS }, style: style };
      }
      if (shape === 'diamond') {
        var r = MARKER_RADIUS + 1.5;
        return {
          type: 'polygon',
          shape: { points: [[x, y - r], [x + r, y], [x, y + r], [x - r, y]] },
          style: style,
        };
      }
      return {
        type: 'rect',
        shape: { x: x - MARKER_RADIUS, y: y - MARKER_RADIUS, width: MARKER_RADIUS * 2, height: MARKER_RADIUS * 2 },
        style: style,
      };
    };
  }

  function batteryVoltageOption(data) {
    var c = data.constants;
    var series = data.series;
    var colors = {
      start: token('--chart-start'),
      min: token('--chart-min'),
      end: token('--chart-end'),
    };
    var span = data.slots.map(function (slot, i) {
      var known = [series.start[i], series.min[i], series.end[i]].filter(function (v) {
        return v !== null;
      });
      return known.length > 1 ? [i, Math.min.apply(null, known), Math.max.apply(null, known)] : [i, null, null];
    });
    var lowest = data.slots.map(function (slot, i) {
      var known = [series.start[i], series.min[i], series.end[i]].filter(function (v) {
        return v !== null;
      });
      return [i, known.length ? Math.min.apply(null, known) : null, data.end_reason_label[i]];
    });
    function markerSeries(name, field, shape, shift) {
      return {
        type: 'custom',
        name: name,
        silent: true,
        itemStyle: { color: colors[field] },
        data: series[field].map(function (v, i) {
          return [i, v];
        }),
        encode: { x: 0, y: 1 },
        renderItem: marker(shape, colors[field], shift),
      };
    }
    var line = function (value, text) {
      return {
        yAxis: value,
        label: { formatter: text + ' ' + comma(value, 1) + ' В', position: 'insideEndTop', color: token('--chart-reference') },
        lineStyle: { type: 'dashed', color: token('--chart-reference') },
      };
    };
    var frame = frameSeries(data, {
      silent: true,
      symbol: 'none',
      data: [line(c.cutoff_v, 'Відсічка'), line(c.full_charge_v, 'Повний заряд')],
    });
    return {
      animation: false,
      grid: { left: 8, right: 14, top: 44, bottom: 56, containLabel: true },
      legend: {
        top: 0,
        data: [
          { name: 'На початку', icon: 'circle' },
          { name: 'Мінімум', icon: 'diamond' },
          { name: 'Наприкінці', icon: 'rect' },
        ],
        textStyle: { color: token('--color-text') },
      },
      xAxis: xAxis(data),
      yAxis: {
        type: 'value',
        name: 'В',
        min: c.cutoff_v - AXIS_PADDING,
        max: c.full_charge_v + AXIS_PADDING,
        scale: true,
        axisLabel: { color: token('--color-muted'), formatter: axisNumber },
      },
      tooltip: tooltipOption(data, function (i) {
        var seq = data.slots[i].seq;
        function volts(value) {
          return value === null ? null : comma(value, 2) + ' В';
        }
        function withCell(value, cell) {
          return value === null ? null : comma(value, 2) + ' В (' + comma(cell, 2) + ' В на банку)';
        }
        var rows = [
          row('Напруга на початку', withCell(series.start[i], data.per_cell.start[i]), reasonFor(data, seq, 'start')),
          row('Мінімальна напруга', withCell(series.min[i], data.per_cell.min[i]), reasonFor(data, seq, 'min')),
          row('Напруга наприкінці', withCell(series.end[i], data.per_cell.end[i]), reasonFor(data, seq, 'end')),
          row('Просадка', volts(data.drop[i]), reasonFor(data, seq, 'drop')),
        ];
        if (data.end_reason_label[i]) {
          rows.push(row('Причина завершення', data.end_reason_label[i], ''));
        }
        return rows;
      }),
      series: [
        frame,
        gapSeries(data),
        {
          type: 'custom',
          name: 'Відрізок',
          silent: true,
          data: span,
          encode: { x: 0, y: [1, 2] },
          renderItem: function (params, api) {
            if (api.value(1) === null || api.value(1) === undefined) {
              return null;
            }
            var from = api.coord([api.value(0), api.value(1)]);
            var to = api.coord([api.value(0), api.value(2)]);
            return {
              type: 'line',
              shape: { x1: from[0], y1: from[1], x2: to[0], y2: to[1] },
              style: { stroke: token('--chart-reference'), lineWidth: 1 },
            };
          },
        },
        markerSeries('На початку', 'start', 'circle', -MARKER_SHIFT),
        markerSeries('Мінімум', 'min', 'diamond', 0),
        markerSeries('Наприкінці', 'end', 'rect', MARKER_SHIFT),
        {
          type: 'custom',
          name: 'Причина завершення',
          silent: true,
          data: lowest,
          encode: { x: 0, y: 1 },
          renderItem: function (params, api) {
            var label = api.value(2);
            if (!label || api.value(1) === null) {
              return null;
            }
            var point = api.coord([api.value(0), api.value(1)]);
            return {
              type: 'text',
              style: {
                text: label,
                x: point[0],
                y: point[1] + 12,
                width: 84,
                overflow: 'break',
                align: 'center',
                verticalAlign: 'top',
                fontSize: 11,
                fill: token('--chart-min'),
              },
            };
          },
        },
        hitSeries(data),
      ],
    };
  }

  function batteryDropOption(data) {
    var bars = data.drop.map(function (value, i) {
      if (value === null) {
        return null;
      }
      if (data.largest_drop_seq === data.slots[i].seq) {
        return { value: value, label: { show: true, position: 'top', formatter: 'найбільша просадка', color: token('--color-text') } };
      }
      return value;
    });
    return {
      animation: false,
      grid: { left: 8, right: 14, top: 36, bottom: 56, containLabel: true },
      xAxis: xAxis(data),
      yAxis: {
        type: 'value',
        name: 'В',
        min: 0,
        axisLabel: { color: token('--color-muted'), formatter: axisNumber },
      },
      tooltip: tooltipOption(data, function (i) {
        var value = data.drop[i];
        return [
          row(
            'Просадка (початкова мінус мінімальна)',
            value === null ? null : comma(value, 2) + ' В',
            reasonFor(data, data.slots[i].seq, 'drop')
          ),
        ];
      }),
      series: [
        {
          type: 'bar',
          name: 'Просадка',
          data: bars,
          barMaxWidth: 28,
          itemStyle: { color: token('--chart-drop') },
        },
        gapSeries(data),
        hitSeries(data),
      ],
    };
  }

  function renderBattery(section, data) {
    mount(section, 'battery-voltage', batteryVoltageOption(data));
    mount(section, 'battery-drop', batteryDropOption(data));
  }

  // ---------- Блок «Перешкоди» ----------

  // Штрихування кольору «немає даних»: відрізняється від рамки «утримань не було».
  function hatch() {
    var canvas = document.createElement('canvas');
    canvas.width = 8;
    canvas.height = 8;
    var ctx = canvas.getContext('2d');
    ctx.strokeStyle = token('--color-no-data');
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, 8);
    ctx.lineTo(8, 0);
    ctx.stroke();
    return { image: canvas, repeat: 'repeat' };
  }

  // Слоти без стовпця: «утримань не було» — тонка суцільна рамка без заливки,
  // «немає даних» — штрихована заливка з причиною вздовж слота. rows: [{i, kind, text}].
  function slotStates(rows) {
    return {
      type: 'custom',
      name: 'Стан слота',
      silent: true,
      data: rows.map(function (r) {
        return [r.i, r.kind];
      }),
      encode: { x: 0 },
      renderItem: function (params, api) {
        var row = rows[params.dataIndex];
        var area = params.coordSys;
        var width = api.size([1, 0])[0];
        var center = api.coord([api.value(0), 0])[0];
        var frame = row.kind === 'no_holds';
        var height = frame ? area.height * 0.7 : area.height;
        var top = area.y + area.height - height;
        var rect = {
          type: 'rect',
          shape: { x: center - width * 0.4, y: top, width: width * 0.8, height: height },
          style: frame
            ? { fill: 'none', stroke: token('--chart-reference'), lineWidth: 1 }
            : { fill: hatch(), stroke: token('--color-no-data'), lineWidth: 1 },
        };
        var text = {
          type: 'text',
          x: center,
          y: top + height / 2,
          rotation: Math.PI / 2,
          style: {
            text: row.text,
            x: 0,
            y: 0,
            align: 'center',
            verticalAlign: 'middle',
            fontSize: 11,
            fill: frame ? token('--chart-reference') : token('--color-no-data'),
            fontStyle: frame ? 'normal' : 'italic',
          },
        };
        return { type: 'group', children: [rect, text] };
      },
    };
  }

  function obstaclesTooltip(data) {
    return tooltipOption(data, function (i) {
      var seq = data.slots[i].seq;
      var distance = data.distance_mm[i];
      var distanceText = null;
      if (distance !== null) {
        distanceText = distance + ' мм';
      } else if (data.no_holds[i]) {
        distanceText = 'утримань не було';
      }
      var sensorText = null;
      if (data.sensor[i] !== null) {
        // Невідомий датчик: сире значення лише як текст підказки (textContent у `row`).
        sensorText = data.sensor_raw[i] !== null ? data.sensor[i] + ' (' + data.sensor_raw[i] + ')' : data.sensor[i];
      }
      var off = data.control_off_s[i];
      var rows = [row('Найменша відстань', distanceText, reasonFor(data, seq, 'distance'))];
      if (sensorText !== null) {
        rows.push(row('Датчик', sensorText, ''));
      }
      rows.push(row('Захист вимкнено', off === null ? null : comma(off, off === 0 ? 0 : 1) + ' с', reasonFor(data, seq, 'control_off')));
      return rows;
    });
  }

  function obstaclesDistanceOption(data) {
    var threshold = data.constants.obstacle_threshold_mm;
    var rows = [];
    var top = threshold;
    var bars = data.distance_mm.map(function (value, i) {
      if (data.slots[i].gap) {
        return null;
      }
      if (value !== null) {
        top = Math.max(top, value);
        return {
          value: value,
          label: { show: true, position: 'top', formatter: data.sensor[i], color: token('--color-text'), fontSize: 11 },
        };
      }
      if (data.no_holds[i]) {
        rows.push({ i: i, kind: 'no_holds', text: 'утримань не було' });
      } else {
        rows.push({ i: i, kind: 'no_data', text: NO_DATA });
      }
      return null;
    });
    return {
      animation: false,
      grid: { left: 8, right: 14, top: 36, bottom: 56, containLabel: true },
      xAxis: xAxis(data),
      yAxis: {
        type: 'value',
        name: 'мм',
        min: 0,
        max: Math.ceil(top * 1.25),
        axisLabel: { color: token('--color-muted'), formatter: axisNumber },
      },
      tooltip: obstaclesTooltip(data),
      series: [
        {
          type: 'bar',
          name: 'Найменша відстань',
          data: bars,
          barMaxWidth: 28,
          itemStyle: { color: token('--chart-distance') },
          markLine: {
            silent: true,
            symbol: 'none',
            data: [
              {
                yAxis: threshold,
                label: { formatter: 'Поріг ' + threshold + ' мм', position: 'insideEndTop', color: token('--chart-reference') },
                lineStyle: { type: 'dashed', color: token('--chart-reference') },
              },
            ],
          },
        },
        slotStates(rows),
        gapSeries(data),
        hitSeries(data),
      ],
    };
  }

  function obstaclesControlOffOption(data) {
    var rows = [];
    var bars = data.control_off_s.map(function (value, i) {
      if (data.slots[i].gap) {
        return null;
      }
      if (value === null) {
        rows.push({ i: i, kind: 'no_data', text: NO_DATA });
        return null;
      }
      return {
        value: value,
        label: { show: true, position: 'top', formatter: comma(value, value === 0 ? 0 : 1) + ' с', color: token('--color-text'), fontSize: 11 },
      };
    });
    return {
      animation: false,
      grid: { left: 8, right: 14, top: 36, bottom: 56, containLabel: true },
      xAxis: xAxis(data),
      yAxis: { type: 'value', name: 'с', min: 0, axisLabel: { color: token('--color-muted'), formatter: axisNumber } },
      tooltip: obstaclesTooltip(data),
      series: [
        { type: 'bar', name: 'Захист вимкнено', data: bars, barMaxWidth: 28, itemStyle: { color: token('--chart-control-off') } },
        slotStates(rows),
        gapSeries(data),
        hitSeries(data),
      ],
    };
  }

  function renderObstacles(section, data) {
    mount(section, 'obstacles-distance', obstaclesDistanceOption(data));
    mount(section, 'obstacles-control-off', obstaclesControlOffOption(data));
  }

  // ---------- Запуск: кожен блок ізольовано ----------

  var RENDERERS = {
    battery: renderBattery,
    obstacles: renderObstacles,
  };

  function unavailable(section) {
    var elements = section.querySelectorAll('.chart');
    for (var i = 0; i < elements.length; i++) {
      elements[i].hidden = false;
      elements[i].textContent = UNAVAILABLE;
    }
  }

  function startBlock(section) {
    try {
      var key = section.getAttribute('data-chart-block');
      if (typeof echarts === 'undefined' || !RENDERERS[key]) {
        throw new Error('charts unavailable');
      }
      var data = JSON.parse(document.getElementById('chart-data-' + key).textContent);
      RENDERERS[key](section, data);
    } catch (error) {
      unavailable(section);
    }
  }

  function start() {
    var sections = document.querySelectorAll('[data-chart-block][data-state="ok"]');
    for (var i = 0; i < sections.length; i++) {
      startBlock(sections[i]);
    }
    window.addEventListener('resize', function () {
      charts.forEach(function (c) {
        c.chart.resize();
      });
    });
    // Дотик чи клік поза графіком ховає підказку (AC-18).
    function hideOutside(event) {
      charts.forEach(function (c) {
        if (!c.element.contains(event.target)) {
          c.chart.dispatchAction({ type: 'hideTip' });
        }
      });
    }
    document.addEventListener('touchstart', hideOutside, { passive: true });
    document.addEventListener('click', hideOutside);
  }

  start();
})();
